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
    except Exception as e:
        logger.warning("Carbon metrics refresh failed (non-fatal): %s", e)
