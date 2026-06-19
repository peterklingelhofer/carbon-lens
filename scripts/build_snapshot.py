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
from carbon_mesh.models.carbon import CarbonIntensity


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


class _PrefetchedSource:
    """Serves this run's already-fetched intensities in-memory, so signal precompute
    reuses snapshot data instead of re-hitting upstream provider APIs for the current
    reading. Forecasts still come from the (free) ENTSO-E / Open-Meteo forecast sources."""

    def __init__(self, by_zone: dict[str, CarbonIntensity]) -> None:
        self._by_zone = by_zone

    async def get_carbon_intensity(self, grid_zone: str) -> CarbonIntensity:
        ci = self._by_zone.get(grid_zone)
        if ci is None:
            raise KeyError(f"no prefetched intensity for zone {grid_zone}")
        return ci

    async def get_carbon_intensity_batch(self, grid_zones: list[str]) -> dict[str, CarbonIntensity]:
        return {z: self._by_zone[z] for z in grid_zones if z in self._by_zone}


def _ci_from_entry(entry: dict) -> CarbonIntensity:
    """Reconstruct a CarbonIntensity from a published snapshot entry (covers
    carried-forward zones too, which aren't in this run's fresh fetch)."""
    return CarbonIntensity(
        grid_zone=entry["grid_zone"],
        carbon_intensity_gco2_kwh=entry["carbon_intensity_gco2_kwh"],
        renewable_percentage=entry["renewable_percentage"],
        timestamp=datetime.fromisoformat(entry["timestamp"]),
        source=entry["source"],
        grid_load_mw=entry.get("grid_load_mw"),
        marginal_intensity_gco2_kwh=entry.get("marginal_intensity_gco2_kwh"),
        power_breakdown_mw=entry.get("power_breakdown_mw"),
    )


_UNSET = object()


async def compute_region_data(
    snapshot_intensities: dict[str, dict],
    region_meta: dict[str, dict],
    mapper: GridMapper,
    forecast_source=_UNSET,
    weather_forecast_source=_UNSET,
) -> dict[str, dict]:
    """Precompute the run-now/wait signal AND the 24h forecast curve per published region.

    Both reuse the exact same engine the live API uses (so the static CDN data matches),
    and the forecast is computed once per grid zone and shared by the signal and the
    published curve, then fanned out to every region sharing the zone. Best-effort: a
    zone whose forecast fails is simply omitted. Forecast sources are injectable (pass
    None for both) so tests run without network.

    Returns ``{"signals": {key: signal}, "forecasts": {key: forecast}}``."""
    from carbon_mesh.carbon_sources.entsoe_forecast import ENTSOEForecastSource
    from carbon_mesh.carbon_sources.open_meteo import OpenMeteoForecastSource
    from carbon_mesh.engine.signal import build_signal
    from carbon_mesh.engine.surplus import surplus_offsets
    from carbon_mesh.scheduler.engine import SchedulingEngine

    if forecast_source is _UNSET:
        forecast_source = ENTSOEForecastSource(settings.entsoe_token)
    if weather_forecast_source is _UNSET:
        weather_forecast_source = OpenMeteoForecastSource()

    by_zone: dict[str, CarbonIntensity] = {}
    zone_keys: dict[str, list[str]] = {}
    for key, entry in snapshot_intensities.items():
        zone = entry["grid_zone"]
        by_zone.setdefault(zone, _ci_from_entry(entry))
        zone_keys.setdefault(zone, []).append(key)

    prefetched = _PrefetchedSource(by_zone)
    engine = SchedulingEngine(
        carbon_source=prefetched,
        grid_mapper=mapper,
        forecast_source=forecast_source,
        weather_forecast_source=weather_forecast_source,
        marginal_source=None,  # public snapshot: heuristic marginal only
    )

    signals: dict[str, dict] = {}
    forecasts: dict[str, dict] = {}
    forecasts_week: dict[str, dict] = {}

    def _compact(pts):
        return [
            {"t": p.timestamp.isoformat(), "c": round(p.carbon_intensity_gco2_kwh, 1)} for p in pts
        ]

    for zone, keys in zone_keys.items():
        rep = region_meta.get(keys[0], {})
        lon = rep.get("longitude") or 0.0
        try:
            # One 7-day projection: the first 24h drives the panel forecast + signal (so
            # they match the 24h API exactly), the full 168h feeds the week heatmap.
            method, points = await engine.forecast_zone(zone, lon, 168)
        except Exception as e:
            print(f"  (forecast for {zone} unavailable: {e})", file=sys.stderr)
            continue

        points24 = points[:25]
        fc_base = {
            "grid_zone": zone,
            "method": method,
            "generated_at": points[0].timestamp.isoformat() if points else None,
            "clean_surplus_hours": surplus_offsets(points24),
            "points": _compact(points24),
        }
        week_base = {
            "grid_zone": zone,
            "method": method,
            "generated_at": points[0].timestamp.isoformat() if points else None,
            "points": _compact(points),
        }

        sig_base: dict | None = None
        try:
            sig = await build_signal(
                rep.get("provider", ""),
                rep.get("region", ""),
                zone,
                lon,
                engine,
                prefetched,
                points=points24,
            )
            sig_base = sig.model_dump()
        except Exception as e:
            print(f"  (signal for {zone} unavailable: {e})", file=sys.stderr)

        for key in keys:
            m = region_meta.get(key, {})
            prov, reg = m.get("provider", ""), m.get("region", "")
            forecasts[key] = {**fc_base, "provider": prov, "region": reg}
            forecasts_week[key] = {**week_base, "provider": prov, "region": reg}
            if sig_base is not None:
                signals[key] = {
                    **sig_base,
                    "provider": prov or sig_base["provider"],
                    "region": reg or sig_base["region"],
                }
    return {"signals": signals, "forecasts": forecasts, "forecasts_week": forecasts_week}


async def compute_weather(region_meta: dict[str, dict], fetch=_UNSET, concurrency: int = 8) -> dict:
    """Precompute current wind/solar per region (Open-Meteo) so the frontend reads the
    weather drivers from the CDN, not the live API. Concurrency-limited and best-effort:
    a region whose fetch fails (or lacks coordinates) is simply omitted. ``fetch`` is
    injectable (the Open-Meteo call) so tests run without network."""
    import asyncio

    if fetch is _UNSET:
        from carbon_mesh.carbon_sources.open_meteo import fetch_weather

        fetch = fetch_weather

    sem = asyncio.Semaphore(concurrency)
    out: dict[str, dict] = {}

    async def _one(key: str, meta: dict) -> None:
        lat, lon = meta.get("latitude"), meta.get("longitude")
        if lat is None or lon is None:
            return
        async with sem:
            try:
                wind, solar = await fetch(lat, lon)
            except Exception:
                return
        out[key] = {
            "wind_speed_kmh": round(wind, 1),
            "solar_irradiance_w_m2": round(solar),
            "source": "open_meteo",
        }

    await asyncio.gather(*[_one(k, m) for k, m in region_meta.items()])
    return out


async def build_snapshot(
    baseline: dict | None = None, max_stale_hours: float = 6.0, with_signals: bool = True
) -> dict:
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

    # Precompute the run-now/wait signal and 24h forecast per region so the frontend and
    # SDK can read decisions and curves straight from the CDN -- no live API, no cold
    # start. Best-effort: a failure here never blocks publishing the snapshot itself.
    signals: dict[str, dict] = {}
    forecasts: dict[str, dict] = {}
    forecasts_week: dict[str, dict] = {}
    weather: dict[str, dict] = {}
    if with_signals:
        published_meta = {k: region_meta[k] for k in snapshot_intensities if k in region_meta}
        try:
            data = await compute_region_data(snapshot_intensities, region_meta, mapper)
            signals, forecasts, forecasts_week = (
                data["signals"],
                data["forecasts"],
                data["forecasts_week"],
            )
        except Exception as e:
            print(f"  (signal/forecast precompute skipped: {e})", file=sys.stderr)
        try:
            weather = await compute_weather(published_meta)
        except Exception as e:
            print(f"  (weather precompute skipped: {e})", file=sys.stderr)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "regions": snapshot_regions,
        "intensities": snapshot_intensities,
        "signals": signals,
        "forecasts": forecasts,
        "weather": weather,
        "best_time": {},  # filled in by _main once the rolling history is built
        # The 7-day curve per region is big and only the Scheduler heatmap needs it, so
        # _main pops this out to its own lazy-loaded forecast_week.json -- it never ships
        # in the site-wide snapshot.json.
        "forecast_week": forecasts_week,
        "summary": {
            "live_zones": counts["live"],
            "estimated_zones": counts["estimated"],
            "mock_zones_dropped": counts["mock"],
            "carried_forward": carried,
            "regions_published": len(snapshot_regions),
            "signals_published": len(signals),
            "forecasts_published": len(forecasts),
            "weather_published": len(weather),
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


def compute_best_times(
    history: dict, forecasts: dict, regions: list[dict], days: int = 14
) -> dict[str, dict]:
    """Precompute the greenest-hour BestTime per region from the rolling history archive
    (with each region's 24h forecast curve as the thin-history fallback), reusing the same
    ``engine.besttime.build_best_time`` the live endpoint uses so the static result matches."""
    from carbon_mesh.engine.besttime import build_best_time

    series = history.get("series", {})
    out: dict[str, dict] = {}
    for r in regions:
        key = f"{r['provider']}/{r['region']}"
        raw = series.get(key, [])
        fc_points = forecasts.get(key, {}).get("points", [])
        bt = build_best_time(r["provider"], r["region"], r["grid_zone"], raw, fc_points, days)
        out[key] = bt.model_dump()
    return out


def history_to_csv(history: dict) -> str:
    """Flatten the rolling history archive into a tidy CSV open dataset -- one row
    per (region, hour), so anyone can download and analyse it without our JSON shape."""
    import csv
    import io

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        ["provider", "region", "timestamp", "carbon_intensity_gco2_kwh", "renewable_percentage"]
    )
    for key, points in sorted(history.get("series", {}).items()):
        provider, _, region = key.partition("/")
        for p in points:
            writer.writerow([provider, region, p.get("t", ""), p.get("c", ""), p.get("r", "")])
    return buf.getvalue()


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
    parser.add_argument(
        "--no-signals",
        action="store_true",
        help="Skip precomputing per-region run-now/wait signals (faster local builds)",
    )
    parser.add_argument(
        "--forecast-week-out",
        default="forecast_week.json",
        help="Lazy-loaded 7-day per-region forecast (for the clean-window heatmap); '' to skip",
    )
    args = parser.parse_args()

    baseline = _load_baseline(args.baseline)
    snapshot = await build_snapshot(
        baseline=baseline,
        max_stale_hours=args.max_stale_hours,
        with_signals=not args.no_signals,
    )

    # Build the rolling history first so we can fold the greenest-hour BestTime into the
    # snapshot too (it ranks history, with each region's forecast curve as the fallback).
    prev_history = _load_baseline(args.history_baseline) if args.history_baseline else {}
    history = append_history(prev_history, snapshot)
    if not args.no_signals:
        snapshot["best_time"] = compute_best_times(
            history, snapshot.get("forecasts", {}), snapshot["regions"]
        )
        snapshot["summary"]["best_time_published"] = len(snapshot["best_time"])

    # The 7-day forecast is large and only the heatmap needs it -> its own lazy file,
    # never in the site-wide snapshot.json.
    forecast_week = snapshot.pop("forecast_week", {})
    if args.forecast_week_out and forecast_week:
        with open(args.forecast_week_out, "w") as f:
            json.dump({"forecasts": forecast_week}, f, separators=(",", ":"))
        print(f"Wrote {args.forecast_week_out}: {len(forecast_week)} region week-forecasts")

    with open(args.out, "w") as f:
        json.dump(snapshot, f, indent=2)

    if args.history_out:
        with open(args.history_out, "w") as f:
            json.dump(history, f, separators=(",", ":"))
        # Publish the same data as a tidy CSV open dataset (history.csv) for anyone
        # to download and analyse.
        csv_out = (
            args.history_out[:-5] + ".csv"
            if args.history_out.endswith(".json")
            else args.history_out + ".csv"
        )
        with open(csv_out, "w", newline="") as f:
            f.write(history_to_csv(history))
        print(f"Wrote {args.history_out} + {csv_out}: {len(history['series'])} regions tracked")

    s = snapshot["summary"]
    print(
        f"Wrote {args.out}: {s['regions_published']} regions "
        f"({s['live_zones']} live zones, {s['estimated_zones']} estimated, "
        f"{s['mock_zones_dropped']} mock dropped, {s['carried_forward']} carried forward, "
        f"{s.get('signals_published', 0)} signals)"
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
