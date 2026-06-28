"""Background SLA monitor — continuously checks SLAs and sends alerts."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx

from carbon_mesh.models.sla import (
    AlertChannel,
    AlertEvent,
    GreenSLA,
    SLACheck,
    SLAStatus,
)
from carbon_mesh.sla.engine import FREQUENCY_SECONDS, SLAEngine, is_due

logger = logging.getLogger(__name__)

__all__ = ["FREQUENCY_SECONDS", "SLAMonitor"]


class SLAMonitor:
    """Background worker that periodically checks SLA compliance.

    Designed to run as a long-lived asyncio task. Checks each active SLA
    at its configured frequency and sends alerts on breach.
    """

    def __init__(self, engine: SLAEngine) -> None:
        self._engine = engine
        self._running = False
        self._task: asyncio.Task | None = None
        self._last_check: dict[str, datetime] = {}  # sla_id -> last checked time
        self._alerts_sent: list[AlertEvent] = []  # bounded list of recent alerts
        self._checks_completed: int = 0
        self._breaches_detected: int = 0

    async def start(self, slas: list[GreenSLA]) -> None:
        """Start the background monitor for the given SLAs."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop(slas))
        logger.info("SLA monitor started for %d SLAs", len(slas))

    async def stop(self) -> None:
        """Stop the background monitor."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("SLA monitor stopped")

    @property
    def running(self) -> bool:
        return self._running

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "checks_completed": self._checks_completed,
            "breaches_detected": self._breaches_detected,
            "slas_monitored": len(self._last_check),
            "recent_alerts": len(self._alerts_sent),
        }

    def get_recent_alerts(self, limit: int = 50) -> list[AlertEvent]:
        return self._alerts_sent[-limit:]

    async def _run_loop(self, slas: list[GreenSLA]) -> None:
        """Main monitoring loop — checks SLAs at their configured frequency."""
        # Check every 60 seconds to see if any SLAs are due
        poll_interval = 60

        while self._running:
            try:
                now = datetime.now(UTC)
                for sla in slas:
                    if not sla.active:
                        continue

                    # Check if this SLA is due for a check
                    if not is_due(self._last_check.get(sla.id), sla.check_frequency, now):
                        continue

                    # Run the check
                    try:
                        check = await self._engine.check_sla(sla)
                        self._last_check[sla.id] = now
                        self._checks_completed += 1

                        logger.info(
                            "SLA check [%s]: %s (carbon=%.1f, renewable=%.1f%%)",
                            sla.name,
                            check.status.value,
                            check.avg_carbon_intensity_gco2_kwh,
                            check.avg_renewable_percentage,
                        )

                        # Send alerts on breach
                        if check.status in (SLAStatus.BREACHED, SLAStatus.WARNING):
                            self._breaches_detected += 1
                            await self._send_alerts(sla, check)

                    except Exception as e:
                        logger.error("SLA check failed for [%s]: %s", sla.name, e)

                await asyncio.sleep(poll_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("SLA monitor loop error: %s", e)
                await asyncio.sleep(poll_interval)

    async def _send_alerts(self, sla: GreenSLA, check: SLACheck) -> None:
        """Send alerts through configured channels."""
        for channel in sla.alert_channels:
            try:
                if channel == AlertChannel.WEBHOOK and sla.webhook_url:
                    await self._send_webhook(sla, check)

                alert = AlertEvent(
                    id=str(uuid.uuid4()),
                    sla_id=sla.id,
                    sla_name=sla.name,
                    channel=channel,
                    sent_at=datetime.now(UTC),
                    status=check.status,
                    details={
                        "avg_carbon": check.avg_carbon_intensity_gco2_kwh,
                        "avg_renewable": check.avg_renewable_percentage,
                        "regions_breached": check.regions_breached,
                        "breached_regions": check.breached_regions[:5],
                    },
                )
                self._alerts_sent.append(alert)

                # Keep bounded
                if len(self._alerts_sent) > 1000:
                    self._alerts_sent = self._alerts_sent[-500:]

            except Exception as e:
                logger.error("Failed to send %s alert for SLA [%s]: %s", channel.value, sla.name, e)

    async def _send_webhook(self, sla: GreenSLA, check: SLACheck) -> None:
        """Send a webhook notification for an SLA breach."""
        payload = {
            "event": "sla_breach",
            "sla_id": sla.id,
            "sla_name": sla.name,
            "status": check.status.value,
            "checked_at": check.checked_at.isoformat(),
            "avg_carbon_intensity_gco2_kwh": check.avg_carbon_intensity_gco2_kwh,
            "avg_renewable_percentage": check.avg_renewable_percentage,
            "regions_breached": check.regions_breached,
            "regions_checked": check.regions_checked,
            "breached_regions": check.breached_regions[:10],
            "target_max_carbon": check.target_max_carbon,
            "target_min_renewable": check.target_min_renewable,
        }

        _parsed = urlparse(sla.webhook_url)
        if _parsed.scheme not in ("http", "https") or not _parsed.netloc:
            logger.warning(
                "Skipping webhook for SLA [%s]: invalid URL %r", sla.name, sla.webhook_url
            )
            return
        if _parsed.hostname in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
            logger.warning("Skipping webhook for SLA [%s]: localhost target blocked", sla.name)
            return

        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(sla.webhook_url, json=payload)
            response.raise_for_status()
            logger.info(
                "Webhook sent for SLA [%s] to %s: %d",
                sla.name,
                sla.webhook_url,
                response.status_code,
            )
