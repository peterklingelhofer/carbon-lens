"""Build a static carbon snapshot from real providers for the public demo.

Run on a schedule by CI. The resulting JSON is published to a CDN and read
directly by the frontend, so user traffic never hits upstream provider APIs:
quota cost is O(zones x cadence), not O(users).

Quality is derived from each reading's ``source`` field:
  live      real grid-operator API (EIA, ENTSO-E, UK, AEMO, GridStatus, Grid India, ONS Brazil)
  estimated heuristic or weather-derived model (``*_heuristic``, Open-Meteo)
  mock      static fallback -- dropped from the snapshot entirely

Usage:
    uv run python scripts/build_snapshot.py --out snapshot.json
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone

from carbon_mesh.carbon_sources.eia import EIACarbonSource
from carbon_mesh.carbon_sources.electricity_maps import ElectricityMapsCarbonSource
from carbon_mesh.carbon_sources.entsoe import ENTSOECarbonSource
from carbon_mesh.carbon_sources.gridstatus import GridStatusCarbonSource
from carbon_mesh.carbon_sources.hybrid import HybridCarbonSource
from carbon_mesh.config import settings
from carbon_mesh.grid.mapper import GridMapper


def _quality(source: str) -> str:
    """Bucket a provider source string into live / estimated / mock."""
    if source.endswith("_heuristic") or source == "open_meteo":
        return "estimated"
    if source in {"mock", "electricity_maps_error"}:
        return "mock"
    return "live"


def _build_source() -> HybridCarbonSource:
    """Build the hybrid cascade with whatever keys are present in the env."""
    eia = EIACarbonSource(api_key=settings.eia_api_key) if settings.eia_api_key else None
    gridstatus = (
        GridStatusCarbonSource(api_key=settings.grid_status_api_key)
        if settings.grid_status_api_key
        else None
    )
    entsoe = (
        ENTSOECarbonSource(security_token=settings.entsoe_token) if settings.entsoe_token else None
    )
    electricity_maps = (
        ElectricityMapsCarbonSource(api_key=settings.electricity_maps_api_key)
        if settings.electricity_maps_api_key
        else None
    )
    return HybridCarbonSource(
        eia=eia,
        gridstatus=gridstatus,
        entsoe=entsoe,
        electricity_maps=electricity_maps,
    )


async def build_snapshot() -> dict:
    mapper = GridMapper(settings.region_map_path)
    source = _build_source()

    regions = mapper.list_regions()

    # Map each grid zone to all region keys that share it (same logic as
    # POST /api/v1/carbon/batch -- multiple regions can map to one zone).
    zone_to_keys: dict[str, list[str]] = {}
    region_meta: dict[str, dict] = {}
    for r in regions:
        key = f"{r.provider}/{r.region}"
        region_meta[key] = {
            "provider": r.provider,
            "region": r.region,
            "grid_zone": r.grid_zone,
            "location": r.location,
            "latitude": r.latitude,
            "longitude": r.longitude,
        }
        zone_to_keys.setdefault(r.grid_zone, []).append(key)

    intensities = await source.get_carbon_intensity_batch(list(zone_to_keys.keys()))

    snapshot_regions: list[dict] = []
    snapshot_intensities: dict[str, dict] = {}
    counts = {"live": 0, "estimated": 0, "mock": 0}
    degraded: list[str] = []

    for zone, intensity in intensities.items():
        quality = _quality(intensity.source)
        counts[quality] += 1
        for key in zone_to_keys.get(zone, []):
            if quality == "mock":
                # Never publish mock data -- it stays out of the demo entirely.
                continue
            if quality == "estimated":
                degraded.append(key)
            snapshot_intensities[key] = {
                "grid_zone": intensity.grid_zone,
                "carbon_intensity_gco2_kwh": round(intensity.carbon_intensity_gco2_kwh, 1),
                "renewable_percentage": round(intensity.renewable_percentage, 1),
                "timestamp": intensity.timestamp.isoformat(),
                "source": intensity.source,
                "quality": quality,
            }
            snapshot_regions.append(region_meta[key])

    snapshot_regions.sort(key=lambda r: (r["provider"], r["region"]))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "regions": snapshot_regions,
        "intensities": snapshot_intensities,
        "summary": {
            "live_zones": counts["live"],
            "estimated_zones": counts["estimated"],
            "mock_zones_dropped": counts["mock"],
            "regions_published": len(snapshot_regions),
            "degraded": sorted(set(degraded)),
        },
    }


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Build the public carbon snapshot")
    parser.add_argument("--out", default="snapshot.json", help="Output path")
    parser.add_argument(
        "--min-live",
        type=int,
        default=1,
        help="Fail (exit 1) if fewer than this many zones resolve to live data",
    )
    args = parser.parse_args()

    snapshot = await build_snapshot()
    with open(args.out, "w") as f:
        json.dump(snapshot, f, indent=2)

    s = snapshot["summary"]
    print(
        f"Wrote {args.out}: {s['regions_published']} regions "
        f"({s['live_zones']} live zones, {s['estimated_zones']} estimated, "
        f"{s['mock_zones_dropped']} mock dropped)"
    )
    if s["degraded"]:
        print(f"  estimated/intermittent: {', '.join(s['degraded'])}")

    if s["live_zones"] < args.min_live:
        print(
            f"ERROR: only {s['live_zones']} live zones (< {args.min_live}). "
            "Check provider API keys / upstream availability.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
