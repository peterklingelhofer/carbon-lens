"""SLA monitoring engine — checks carbon compliance and generates attestation reports."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from carbon_mesh.carbon_sources.base import CarbonDataSource
from carbon_mesh.grid.mapper import GridMapper
from carbon_mesh.models.sla import (
    GreenSLA,
    SLACheck,
    SLAReport,
    SLAStatus,
    SLASummary,
)

logger = logging.getLogger(__name__)


class SLAEngine:
    """Core SLA monitoring engine.

    Checks carbon intensity against SLA targets using live data sources.
    Runs compliance checks, generates attestation reports, and sends alerts.
    """

    def __init__(
        self,
        carbon_source: CarbonDataSource,
        grid_mapper: GridMapper,
    ) -> None:
        self._carbon_source = carbon_source
        self._grid_mapper = grid_mapper

    async def check_sla(self, sla: GreenSLA) -> SLACheck:
        """Run a compliance check against the SLA targets.

        Fetches live carbon intensity for all monitored regions and compares
        against the SLA thresholds.
        """
        # Determine which regions to check
        regions = self._resolve_regions(sla)

        if not regions:
            return SLACheck(
                id=str(uuid.uuid4()),
                sla_id=sla.id,
                checked_at=datetime.now(timezone.utc),
                status=SLAStatus.UNKNOWN,
                avg_carbon_intensity_gco2_kwh=0,
                max_carbon_intensity_gco2_kwh=0,
                min_carbon_intensity_gco2_kwh=0,
                avg_renewable_percentage=0,
                regions_checked=0,
                regions_compliant=0,
                regions_breached=0,
                breached_regions=[],
                target_max_carbon=sla.max_carbon_intensity_gco2_kwh,
                target_min_renewable=sla.min_renewable_percentage,
            )

        # Fetch carbon data for all regions
        zone_map: dict[str, tuple[str, str]] = {}  # zone -> (provider, region)
        zones: list[str] = []
        for provider, region in regions:
            zone = self._grid_mapper.get_grid_zone(provider, region)
            if zone:
                zone_map[zone] = (provider, region)
                if zone not in zones:
                    zones.append(zone)

        intensities = await self._carbon_source.get_carbon_intensity_batch(zones)

        # Evaluate compliance
        breached: list[dict] = []
        carbon_values: list[float] = []
        renewable_values: list[float] = []
        compliant_count = 0

        for zone, intensity in intensities.items():
            provider, region = zone_map.get(zone, ("unknown", "unknown"))
            carbon_values.append(intensity.carbon_intensity_gco2_kwh)
            renewable_values.append(intensity.renewable_percentage)

            is_carbon_ok = intensity.carbon_intensity_gco2_kwh <= sla.max_carbon_intensity_gco2_kwh
            is_renewable_ok = intensity.renewable_percentage >= sla.min_renewable_percentage

            if is_carbon_ok and is_renewable_ok:
                compliant_count += 1
            else:
                breached.append(
                    {
                        "provider": provider,
                        "region": region,
                        "grid_zone": zone,
                        "carbon_intensity_gco2_kwh": intensity.carbon_intensity_gco2_kwh,
                        "renewable_percentage": intensity.renewable_percentage,
                        "carbon_breached": not is_carbon_ok,
                        "renewable_breached": not is_renewable_ok,
                    }
                )

        total = len(intensities)
        breached_count = len(breached)

        # Determine overall status
        if total == 0:
            status = SLAStatus.UNKNOWN
        elif breached_count == 0:
            status = SLAStatus.COMPLIANT
        elif breached_count <= total * 0.2:
            status = SLAStatus.WARNING
        else:
            status = SLAStatus.BREACHED

        return SLACheck(
            id=str(uuid.uuid4()),
            sla_id=sla.id,
            checked_at=datetime.now(timezone.utc),
            status=status,
            avg_carbon_intensity_gco2_kwh=round(sum(carbon_values) / max(len(carbon_values), 1), 2),
            max_carbon_intensity_gco2_kwh=round(max(carbon_values, default=0), 2),
            min_carbon_intensity_gco2_kwh=round(min(carbon_values, default=0), 2),
            avg_renewable_percentage=round(
                sum(renewable_values) / max(len(renewable_values), 1), 1
            ),
            regions_checked=total,
            regions_compliant=compliant_count,
            regions_breached=breached_count,
            breached_regions=breached,
            target_max_carbon=sla.max_carbon_intensity_gco2_kwh,
            target_min_renewable=sla.min_renewable_percentage,
        )

    def generate_report(
        self,
        sla: GreenSLA,
        checks: list[SLACheck],
        org_name: str,
        period_start: datetime,
        period_end: datetime,
    ) -> SLAReport:
        """Generate an attestation report from a series of SLA checks."""
        if not checks:
            return SLAReport(
                id=str(uuid.uuid4()),
                sla_id=sla.id,
                org_id=sla.org_id,
                org_name=org_name,
                sla_name=sla.name,
                period_start=period_start,
                period_end=period_end,
                generated_at=datetime.now(timezone.utc),
                total_checks=0,
                compliant_checks=0,
                warning_checks=0,
                breached_checks=0,
                compliance_percentage=0,
                avg_carbon_intensity_gco2_kwh=0,
                max_carbon_intensity_gco2_kwh=0,
                avg_renewable_percentage=0,
                min_renewable_percentage=0,
                target_max_carbon=sla.max_carbon_intensity_gco2_kwh,
                target_min_renewable=sla.min_renewable_percentage,
            )

        compliant = sum(1 for c in checks if c.status == SLAStatus.COMPLIANT)
        warning = sum(1 for c in checks if c.status == SLAStatus.WARNING)
        breached = sum(1 for c in checks if c.status == SLAStatus.BREACHED)

        carbon_avgs = [c.avg_carbon_intensity_gco2_kwh for c in checks]
        renewable_avgs = [c.avg_renewable_percentage for c in checks]

        # Daily breakdown
        checks_by_day: dict[str, dict] = {}
        for check in checks:
            day = check.checked_at.strftime("%Y-%m-%d")
            if day not in checks_by_day:
                checks_by_day[day] = {
                    "status": check.status.value,
                    "avg_carbon": check.avg_carbon_intensity_gco2_kwh,
                    "avg_renewable": check.avg_renewable_percentage,
                    "checks": 1,
                }
            else:
                entry = checks_by_day[day]
                entry["checks"] += 1
                # Keep worst status
                if check.status == SLAStatus.BREACHED:
                    entry["status"] = "breached"
                elif check.status == SLAStatus.WARNING and entry["status"] == "compliant":
                    entry["status"] = "warning"
                # Running average
                n = entry["checks"]
                entry["avg_carbon"] = round(
                    (entry["avg_carbon"] * (n - 1) + check.avg_carbon_intensity_gco2_kwh) / n, 2
                )
                entry["avg_renewable"] = round(
                    (entry["avg_renewable"] * (n - 1) + check.avg_renewable_percentage) / n, 1
                )

        # Worst/best regions across all checks
        all_breached: dict[str, dict] = {}
        for check in checks:
            for region_info in check.breached_regions:
                key = f"{region_info['provider']}/{region_info['region']}"
                if key not in all_breached or region_info[
                    "carbon_intensity_gco2_kwh"
                ] > all_breached[key].get("max_carbon", 0):
                    all_breached[key] = {
                        **region_info,
                        "max_carbon": region_info["carbon_intensity_gco2_kwh"],
                        "breach_count": all_breached.get(key, {}).get("breach_count", 0) + 1,
                    }
                else:
                    all_breached[key]["breach_count"] = all_breached[key].get("breach_count", 0) + 1

        worst_regions = sorted(
            all_breached.values(),
            key=lambda r: r.get("max_carbon", 0),
            reverse=True,
        )[:10]

        return SLAReport(
            id=str(uuid.uuid4()),
            sla_id=sla.id,
            org_id=sla.org_id,
            org_name=org_name,
            sla_name=sla.name,
            period_start=period_start,
            period_end=period_end,
            generated_at=datetime.now(timezone.utc),
            total_checks=len(checks),
            compliant_checks=compliant,
            warning_checks=warning,
            breached_checks=breached,
            compliance_percentage=round(compliant / len(checks) * 100, 1),
            avg_carbon_intensity_gco2_kwh=round(sum(carbon_avgs) / len(carbon_avgs), 2),
            max_carbon_intensity_gco2_kwh=round(
                max(c.max_carbon_intensity_gco2_kwh for c in checks), 2
            ),
            avg_renewable_percentage=round(sum(renewable_avgs) / len(renewable_avgs), 1),
            min_renewable_percentage=round(min(c.avg_renewable_percentage for c in checks), 1),
            target_max_carbon=sla.max_carbon_intensity_gco2_kwh,
            target_min_renewable=sla.min_renewable_percentage,
            checks_by_day=checks_by_day,
            worst_regions=worst_regions,
            data_sources=list(
                {
                    c.breached_regions[0].get("source", "hybrid")
                    for c in checks
                    if c.breached_regions
                }
                or {"hybrid"}
            ),
        )

    def summarize(self, sla: GreenSLA, last_check: SLACheck | None) -> SLASummary:
        """Create a lightweight summary of an SLA."""
        return SLASummary(
            id=sla.id,
            name=sla.name,
            org_id=sla.org_id,
            status=last_check.status if last_check else SLAStatus.UNKNOWN,
            max_carbon_intensity_gco2_kwh=sla.max_carbon_intensity_gco2_kwh,
            min_renewable_percentage=sla.min_renewable_percentage,
            check_frequency=sla.check_frequency,
            last_checked=last_check.checked_at if last_check else None,
            active=sla.active,
        )

    def _resolve_regions(self, sla: GreenSLA) -> list[tuple[str, str]]:
        """Resolve SLA config to a list of (provider, region) tuples."""
        if sla.regions:
            # Specific regions specified
            result: list[tuple[str, str]] = []
            for provider in sla.providers:
                for region in sla.regions:
                    if self._grid_mapper.get_grid_zone(provider, region):
                        result.append((provider, region))
            return result

        # All regions for the specified providers
        all_regions = self._grid_mapper.list_regions()
        return [(r.provider, r.region) for r in all_regions if r.provider in sla.providers]
