"""Prometheus carbon-intensity gauges.

Exposes live grid data as Prometheus metrics so teams can graph carbon right next
to CPU and latency. Gauges are refreshed on each /metrics scrape from the same
cached/snapshot source the API uses, so scraping never hits upstream quotas
(snapshot reads are in-memory cached). Labelled per grid zone.
"""

from __future__ import annotations

import logging

from prometheus_client import Gauge

from carbon_mesh.config import settings
from carbon_mesh.engine.surplus import is_clean_surplus

logger = logging.getLogger(__name__)

_LABELS = ("provider", "region", "grid_zone")

CARBON_INTENSITY = Gauge(
    "carbon_intensity_gco2_kwh",
    "Current grid carbon intensity (gCO2/kWh)",
    _LABELS,
)
RENEWABLE_PCT = Gauge(
    "carbon_renewable_percentage",
    "Current renewable share of generation (%)",
    _LABELS,
)
MARGINAL_INTENSITY = Gauge(
    "carbon_marginal_intensity_gco2_kwh",
    "Estimated marginal emission factor (gCO2/kWh) -- heuristic from the fuel mix",
    _LABELS,
)
GRID_LOAD_MW = Gauge(
    "carbon_grid_load_mw",
    "Total grid load for the balancing authority (MW)",
    _LABELS,
)
CLEAN_SURPLUS = Gauge(
    "carbon_clean_surplus",
    "1 when the zone looks like clean oversupply now (renewables abundant, near-zero "
    "marginal) -- the highest-value time to run flexible load; else 0. Heuristic. Alert on "
    "this to trigger carbon-aware batch scaling with your existing Prometheus/Alertmanager.",
    _LABELS,
)
CARBON_TIER = Gauge(
    "carbon_intensity_tier",
    "Grid cleanliness tier: 0 = green (clean), 1 = yellow, 2 = red (dirty). For GRADED "
    "autoscaling -- scale a fleet by '2 - tier' so it runs larger when the grid is cleaner, "
    "capturing the yellow-zone savings an on/off surplus signal misses.",
    _LABELS,
)


def intensity_tier(intensity_gco2_kwh: float) -> int:
    """0 green (<=150), 1 yellow (<=400), 2 red -- same thresholds as the signal state."""
    if intensity_gco2_kwh <= 150:
        return 0
    if intensity_gco2_kwh <= 400:
        return 1
    return 2


IMPACT_KG_AVOIDED = Gauge(
    "carbon_impact_kg_avoided",
    "Estimated kg CO2 avoided by carbon-aware runs in the last 30 days, from the "
    "DB-backed org ledger. Dashboard it next to cost so realized savings are visible.",
)
IMPACT_JOBS_SHIFTED = Gauge(
    "carbon_impact_jobs_shifted",
    "Carbon-aware jobs shifted to cleaner windows in the last 30 days (DB-backed ledger).",
)


MARGINAL_UNMAPPED = Gauge(
    "carbon_marginal_unmapped",
    "1 when a measured-marginal credential is configured but no zone is mapped, so the "
    "marginal signal silently falls back to heuristic; else 0. Alert on this -- it's a "
    "misconfiguration, not a choice (run `carbonlens doctor` to see the fix).",
)


def refresh_config_metrics() -> None:
    """Set config-derived gauges (deterministic, no upstream calls). Best-effort."""
    try:
        from carbon_mesh.carbon_sources.marginal import marginal_unmapped

        MARGINAL_UNMAPPED.set(1 if marginal_unmapped(settings) else 0)
    except Exception as e:
        logger.warning("Config metrics refresh failed (non-fatal): %s", e)


async def refresh_impact_metrics() -> None:
    """Repopulate the org-impact gauges from the DB-backed ledger. No-op without a
    database; best-effort so /metrics never errors."""
    if not settings.use_database:
        return
    try:
        from datetime import datetime, timedelta, timezone

        from carbon_mesh.accounting.impact_repo import recent_impacts
        from carbon_mesh.cli.ledger import fleet_summary
        from carbon_mesh.db.engine import AsyncSessionLocal

        now = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as session:
            rows = await recent_impacts(session, now - timedelta(days=30))
        summary = fleet_summary(rows, now, 30)
        IMPACT_KG_AVOIDED.set(summary["total_kg_avoided"])
        IMPACT_JOBS_SHIFTED.set(summary["shifted"])
    except Exception as e:
        logger.warning("Impact metrics refresh failed (non-fatal): %s", e)


async def refresh_carbon_metrics() -> None:
    """Repopulate the carbon gauges from the current snapshot/cached data. Called
    on each scrape; best-effort so /metrics never errors."""
    from carbon_mesh.api.deps import get_carbon_source, get_grid_mapper
    from carbon_mesh.carbon_sources.snapshot_source import SnapshotBackedSource

    try:
        mapper = get_grid_mapper()
        source = get_carbon_source()
        if settings.snapshot_url and settings.carbon_source != "mock":
            source = SnapshotBackedSource(settings.snapshot_url, source)

        # One representative region per zone (multiple regions can share a zone).
        zone_to_region: dict[str, tuple[str, str]] = {}
        for r in mapper.list_regions():
            zone = mapper.get_grid_zone(r.provider, r.region)
            if zone:
                zone_to_region.setdefault(zone, (r.provider, r.region))

        intensities = await source.get_carbon_intensity_batch(list(zone_to_region))
        for zone, ci in intensities.items():
            provider, region = zone_to_region.get(zone, ("", ""))
            labels = {"provider": provider, "region": region, "grid_zone": zone}
            CARBON_INTENSITY.labels(**labels).set(ci.carbon_intensity_gco2_kwh)
            RENEWABLE_PCT.labels(**labels).set(ci.renewable_percentage)
            if ci.marginal_intensity_gco2_kwh is not None:
                MARGINAL_INTENSITY.labels(**labels).set(ci.marginal_intensity_gco2_kwh)
            if ci.grid_load_mw is not None:
                GRID_LOAD_MW.labels(**labels).set(ci.grid_load_mw)
            surplus = is_clean_surplus(
                ci.renewable_percentage,
                ci.carbon_intensity_gco2_kwh,
                ci.marginal_intensity_gco2_kwh,
            )
            CLEAN_SURPLUS.labels(**labels).set(1 if surplus else 0)
            CARBON_TIER.labels(**labels).set(intensity_tier(ci.carbon_intensity_gco2_kwh))
    except Exception as e:
        logger.warning("Carbon metrics refresh failed (non-fatal): %s", e)
