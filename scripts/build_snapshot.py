"""Build a static carbon snapshot from real providers for the public demo.

Run on a schedule by CI. The resulting JSON is published to a CDN and read
directly by the frontend, so user traffic never hits upstream provider APIs:
quota cost is O(zones x cadence), not O(users).

Quality is derived from each reading's ``source`` field:
  live      real grid-operator API (UK, EIA, OpenElectricity/AEMO, IESO/AESO, Taipower, GridStatus, ENTSO-E, Electricity Maps)
  estimated heuristic or weather-derived model (``*_heuristic``, Open-Meteo)
  mock      static fallback -- dropped from the snapshot entirely

Usage:
    uv run python scripts/build_snapshot.py --out snapshot.json
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone

import httpx

from carbon_mesh.carbon_sources.eia import EIACarbonSource
from carbon_mesh.carbon_sources.electricity_maps import ElectricityMapsCarbonSource
from carbon_mesh.carbon_sources.entsoe import ENTSOECarbonSource
from carbon_mesh.carbon_sources.flow_tracing import ConsumptionIntensitySource
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


def _load_baseline(source: str) -> dict:
    """Load the previously published snapshot (URL or file path) for carry-forward.
    Any failure is non-fatal -- we simply skip carry-forward this run."""
    if not source:
        return {}
    try:
        if source.startswith(("http://", "https://")):
            resp = httpx.get(source, timeout=20.0, follow_redirects=True)
            resp.raise_for_status()
            return resp.json()
        with open(source) as f:
            return json.load(f)
    except Exception as e:
        print(f"  (carry-forward baseline unavailable: {e})", file=sys.stderr)
        return {}


def _carry_forward(
    intensities: dict[str, dict],
    region_meta: dict[str, dict],
    baseline: dict | None,
    max_stale_hours: float,
) -> int:
    """Bridge transient upstream blips: when a region would publish an estimate
    (or nothing) this run, keep its last *live* reading from the previous
    snapshot instead -- but only while that reading is still recent. Real data a
    few hours old beats a generic model for a zone we usually measure. Returns
    the number of regions carried forward."""
    if not baseline:
        return 0
    now = datetime.now(timezone.utc)
    cutoff = timedelta(hours=max_stale_hours)
    carried = 0
    for key, prev in baseline.get("intensities", {}).items():
        if key not in region_meta or prev.get("quality") != "live":
            continue
        current = intensities.get(key)
        if current is not None and current.get("quality") == "live":
            continue  # fresh live data this run -- keep it
        try:
            ts = datetime.fromisoformat(prev["timestamp"])
        except (KeyError, ValueError):
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if now - ts > cutoff:
            continue  # last real reading is too old to trust
        intensities[key] = {**prev, "carried_forward": True}
        carried += 1
    return carried


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


async def build_snapshot(baseline: dict | None = None, max_stale_hours: float = 6.0) -> dict:
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

    snapshot_intensities: dict[str, dict] = {}
    counts = {"live": 0, "estimated": 0, "mock": 0}

    for zone, intensity in intensities.items():
        quality = _quality(intensity.source)
        counts[quality] += 1
        for key in zone_to_keys.get(zone, []):
            if quality == "mock":
                # Never publish fresh mock data -- it stays out of the demo.
                continue
            snapshot_intensities[key] = {
                "grid_zone": intensity.grid_zone,
                "carbon_intensity_gco2_kwh": round(intensity.carbon_intensity_gco2_kwh, 1),
                "renewable_percentage": round(intensity.renewable_percentage, 1),
                "timestamp": intensity.timestamp.isoformat(),
                "source": intensity.source,
                "quality": quality,
                "grid_load_mw": intensity.grid_load_mw,
                "marginal_intensity_gco2_kwh": intensity.marginal_intensity_gco2_kwh,
                "power_breakdown_mw": intensity.power_breakdown_mw,
            }

    carried = _carry_forward(snapshot_intensities, region_meta, baseline, max_stale_hours)

    # Consumption-based intensity for European zones via flow tracing. Best-effort
    # and additive: annotates the relevant entries with consumption_intensity and
    # never blocks the build (a failure just omits the extra field).
    if settings.entsoe_token:
        try:
            consumption = await ConsumptionIntensitySource(settings.entsoe_token).compute()
        except Exception:
            consumption = {}
        for entry in snapshot_intensities.values():
            zone = entry.get("grid_zone")
            if zone in consumption:
                entry["consumption_intensity_gco2_kwh"] = consumption[zone]

    # Rebuild the region list from the final published set (carry-forward may have
    # re-added regions that this run's fetch dropped).
    snapshot_regions = sorted(
        (region_meta[k] for k in snapshot_intensities),
        key=lambda r: (r["provider"], r["region"]),
    )
    degraded = sorted(k for k, v in snapshot_intensities.items() if v["quality"] == "estimated")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "regions": snapshot_regions,
        "intensities": snapshot_intensities,
        "summary": {
            "live_zones": counts["live"],
            "estimated_zones": counts["estimated"],
            "mock_zones_dropped": counts["mock"],
            "carried_forward": carried,
            "regions_published": len(snapshot_regions),
            "degraded": degraded,
        },
    }


# Roughly 7 days at the 30-min publish cadence; bounds history.json size per region.
_HISTORY_MAX_POINTS = 336


def append_history(
    prev_history: dict | None, snapshot: dict, max_points: int = _HISTORY_MAX_POINTS
) -> dict:
    """Append this snapshot's readings to the rolling per-region history archive.

    Keyed by the same ``provider/region`` keys as the snapshot; each point is a
    compact ``{"t","c","r"}`` (timestamp, carbon, renewable). Points beyond
    ``max_points`` are dropped so the file stays bounded, and a repeated timestamp
    (a re-run) replaces the last point rather than duplicating it."""
    series: dict[str, list[dict]] = dict((prev_history or {}).get("series", {}))
    generated_at = snapshot["generated_at"]
    for key, entry in snapshot["intensities"].items():
        point = {
            "t": generated_at,
            "c": entry["carbon_intensity_gco2_kwh"],
            "r": entry["renewable_percentage"],
        }
        prev_points = list(series.get(key, []))
        if prev_points and prev_points[-1].get("t") == generated_at:
            prev_points.pop()
        series[key] = (prev_points + [point])[-max_points:]
    return {"generated_at": generated_at, "series": series}


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Build the public carbon snapshot")
    parser.add_argument("--out", default="snapshot.json", help="Output path")
    parser.add_argument(
        "--min-live",
        type=int,
        default=1,
        help="Fail (exit 1) if fewer than this many zones resolve to live data",
    )
    parser.add_argument(
        "--baseline",
        default="https://raw.githubusercontent.com/peterklingelhofer/carbonlens/data/snapshot.json",
        help="Previous snapshot (URL or path) to carry forward from; '' to disable",
    )
    parser.add_argument(
        "--max-stale-hours",
        type=float,
        default=6.0,
        help="Oldest a carried-forward live reading may be before it's dropped",
    )
    parser.add_argument(
        "--history-out",
        default="history.json",
        help="Rolling history archive output path; '' to skip",
    )
    parser.add_argument(
        "--history-baseline",
        default="https://raw.githubusercontent.com/peterklingelhofer/carbonlens/data/history.json",
        help="Previous history archive (URL or path) to append to; '' to disable",
    )
    args = parser.parse_args()

    baseline = _load_baseline(args.baseline)
    snapshot = await build_snapshot(baseline=baseline, max_stale_hours=args.max_stale_hours)
    with open(args.out, "w") as f:
        json.dump(snapshot, f, indent=2)

    if args.history_out:
        prev_history = _load_baseline(args.history_baseline)
        history = append_history(prev_history, snapshot)
        with open(args.history_out, "w") as f:
            json.dump(history, f, separators=(",", ":"))
        print(f"Wrote {args.history_out}: {len(history['series'])} regions tracked")

    s = snapshot["summary"]
    print(
        f"Wrote {args.out}: {s['regions_published']} regions "
        f"({s['live_zones']} live zones, {s['estimated_zones']} estimated, "
        f"{s['mock_zones_dropped']} mock dropped, {s['carried_forward']} carried forward)"
    )
    if s["degraded"]:
        print(f"  estimated/intermittent: {', '.join(s['degraded'])}")

    published_live = sum(1 for v in snapshot["intensities"].values() if v["quality"] == "live")
    if published_live < args.min_live:
        print(
            f"ERROR: only {published_live} live regions published (< {args.min_live}). "
            "Check provider API keys / upstream availability.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
