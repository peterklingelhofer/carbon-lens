"""Green SLA monitoring API endpoints."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from carbon_mesh.api.deps import get_carbon_source, get_grid_mapper
from carbon_mesh.auth.dependencies import require_api_key
from carbon_mesh.models.sla import (
    AlertChannel,
    AlertEvent,
    GreenSLA,
    SLACheck,
    SLACheckFrequency,
    SLAReport,
    SLASummary,
)
from carbon_mesh.sla.engine import SLAEngine
from carbon_mesh.sla.monitor import SLAMonitor

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/v1/sla",
    tags=["SLA Monitoring"],
    dependencies=[Depends(require_api_key)],
)

# In-memory store for MVP
_sla_store: dict[str, GreenSLA] = {}  # sla_id -> SLA
_check_store: dict[str, list[SLACheck]] = {}  # sla_id -> checks
_report_store: dict[str, list[SLAReport]] = {}  # sla_id -> reports

# Singleton monitor
_monitor: SLAMonitor | None = None


def _get_engine() -> SLAEngine:
    return SLAEngine(
        carbon_source=get_carbon_source(),
        grid_mapper=get_grid_mapper(),
    )


def _get_monitor() -> SLAMonitor:
    global _monitor
    if _monitor is None:
        _monitor = SLAMonitor(engine=_get_engine())
    return _monitor


# --- Request models ---


class CreateSLARequest(BaseModel):
    org_id: str
    name: str
    max_carbon_intensity_gco2_kwh: float = Field(ge=0, default=100.0)
    min_renewable_percentage: float = Field(ge=0, le=100, default=50.0)
    providers: list[str] = Field(default_factory=lambda: ["aws", "gcp", "azure"])
    regions: list[str] = Field(default_factory=list)
    check_frequency: SLACheckFrequency = SLACheckFrequency.HOURLY
    alert_channels: list[AlertChannel] = Field(default_factory=list)
    webhook_url: str = ""


class UpdateSLARequest(BaseModel):
    name: str | None = None
    max_carbon_intensity_gco2_kwh: float | None = Field(ge=0, default=None)
    min_renewable_percentage: float | None = Field(ge=0, le=100, default=None)
    providers: list[str] | None = None
    regions: list[str] | None = None
    check_frequency: SLACheckFrequency | None = None
    alert_channels: list[AlertChannel] | None = None
    webhook_url: str | None = None
    active: bool | None = None


class GenerateReportRequest(BaseModel):
    org_name: str
    period_days: int = Field(ge=1, le=365, default=30)


# --- Endpoints ---


@router.post("/create", response_model=GreenSLA)
async def create_sla(req: CreateSLARequest) -> GreenSLA:
    """Create a new Green SLA definition."""
    now = datetime.now(timezone.utc)
    sla = GreenSLA(
        id=str(uuid.uuid4()),
        org_id=req.org_id,
        name=req.name,
        max_carbon_intensity_gco2_kwh=req.max_carbon_intensity_gco2_kwh,
        min_renewable_percentage=req.min_renewable_percentage,
        providers=req.providers,
        regions=req.regions,
        check_frequency=req.check_frequency,
        alert_channels=req.alert_channels,
        webhook_url=req.webhook_url,
        created_at=now,
        updated_at=now,
    )
    _sla_store[sla.id] = sla
    _check_store[sla.id] = []
    return sla


@router.get("/list", response_model=list[SLASummary])
async def list_slas(org_id: str = Query(...)) -> list[SLASummary]:
    """List all SLAs for an organization."""
    engine = _get_engine()
    result: list[SLASummary] = []
    for sla in _sla_store.values():
        if sla.org_id == org_id:
            checks = _check_store.get(sla.id, [])
            last_check = checks[-1] if checks else None
            result.append(engine.summarize(sla, last_check))
    return result


@router.get("/{sla_id}", response_model=GreenSLA)
async def get_sla(sla_id: str) -> GreenSLA:
    """Get an SLA definition by ID."""
    sla = _sla_store.get(sla_id)
    if not sla:
        raise HTTPException(404, f"SLA {sla_id} not found")
    return sla


@router.put("/{sla_id}", response_model=GreenSLA)
async def update_sla(sla_id: str, req: UpdateSLARequest) -> GreenSLA:
    """Update an existing SLA."""
    sla = _sla_store.get(sla_id)
    if not sla:
        raise HTTPException(404, f"SLA {sla_id} not found")

    update_data = req.model_dump(exclude_none=True)
    update_data["updated_at"] = datetime.now(timezone.utc)

    updated = sla.model_copy(update=update_data)
    _sla_store[sla_id] = updated
    return updated


@router.delete("/{sla_id}")
async def delete_sla(sla_id: str) -> dict:
    """Delete an SLA."""
    if sla_id not in _sla_store:
        raise HTTPException(404, f"SLA {sla_id} not found")
    del _sla_store[sla_id]
    _check_store.pop(sla_id, None)
    _report_store.pop(sla_id, None)
    return {"deleted": sla_id}


@router.post("/{sla_id}/check", response_model=SLACheck)
async def check_sla(sla_id: str) -> SLACheck:
    """Run an on-demand SLA compliance check.

    Fetches live carbon data for all monitored regions and evaluates
    against the SLA thresholds.
    """
    sla = _sla_store.get(sla_id)
    if not sla:
        raise HTTPException(404, f"SLA {sla_id} not found")

    engine = _get_engine()
    check = await engine.check_sla(sla)

    if sla_id not in _check_store:
        _check_store[sla_id] = []
    _check_store[sla_id].append(check)

    # Keep bounded (max 10K checks per SLA)
    if len(_check_store[sla_id]) > 10000:
        _check_store[sla_id] = _check_store[sla_id][-5000:]

    return check


@router.get("/{sla_id}/status", response_model=SLACheck | None)
async def get_sla_status(sla_id: str) -> SLACheck | None:
    """Get the most recent compliance check for an SLA."""
    if sla_id not in _sla_store:
        raise HTTPException(404, f"SLA {sla_id} not found")

    checks = _check_store.get(sla_id, [])
    return checks[-1] if checks else None


@router.get("/{sla_id}/checks", response_model=list[SLACheck])
async def list_checks(
    sla_id: str,
    limit: int = Query(50, ge=1, le=1000),
) -> list[SLACheck]:
    """List recent compliance checks for an SLA."""
    if sla_id not in _sla_store:
        raise HTTPException(404, f"SLA {sla_id} not found")

    checks = _check_store.get(sla_id, [])
    return checks[-limit:]


@router.post("/{sla_id}/report", response_model=SLAReport)
async def generate_report(sla_id: str, req: GenerateReportRequest) -> SLAReport:
    """Generate an attestation report for an SLA over a period.

    Uses stored compliance checks to build the report. If no checks exist
    for the period, runs a fresh check first.
    """
    sla = _sla_store.get(sla_id)
    if not sla:
        raise HTTPException(404, f"SLA {sla_id} not found")

    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=req.period_days)
    period_end = now

    # Get checks within period
    checks = [c for c in _check_store.get(sla_id, []) if c.checked_at >= period_start]

    # If no checks exist, run one now
    if not checks:
        engine = _get_engine()
        check = await engine.check_sla(sla)
        if sla_id not in _check_store:
            _check_store[sla_id] = []
        _check_store[sla_id].append(check)
        checks = [check]

    engine = _get_engine()
    report = engine.generate_report(
        sla=sla,
        checks=checks,
        org_name=req.org_name,
        period_start=period_start,
        period_end=period_end,
    )

    if sla_id not in _report_store:
        _report_store[sla_id] = []
    _report_store[sla_id].append(report)

    return report


@router.get("/{sla_id}/reports", response_model=list[SLAReport])
async def list_reports(sla_id: str) -> list[SLAReport]:
    """List all attestation reports for an SLA."""
    if sla_id not in _sla_store:
        raise HTTPException(404, f"SLA {sla_id} not found")
    return _report_store.get(sla_id, [])


# --- Monitor control ---


@router.post("/monitor/start")
async def start_monitor(org_id: str = Query(...)) -> dict:
    """Start the background SLA monitor for an organization's SLAs."""
    slas = [s for s in _sla_store.values() if s.org_id == org_id and s.active]
    if not slas:
        raise HTTPException(404, f"No active SLAs found for org {org_id}")

    monitor = _get_monitor()
    await monitor.start(slas)
    return monitor.get_status()


@router.post("/monitor/stop")
async def stop_monitor() -> dict:
    """Stop the background SLA monitor."""
    monitor = _get_monitor()
    await monitor.stop()
    return monitor.get_status()


@router.get("/monitor/status")
async def monitor_status() -> dict:
    """Get the current status of the SLA monitor."""
    monitor = _get_monitor()
    return monitor.get_status()


@router.get("/monitor/alerts", response_model=list[AlertEvent])
async def list_alerts(limit: int = Query(50, ge=1, le=500)) -> list[AlertEvent]:
    """List recent SLA breach alerts."""
    monitor = _get_monitor()
    return monitor.get_recent_alerts(limit)
