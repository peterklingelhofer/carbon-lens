"""Unit tests for the recently-added infrastructure: snapshot-backed source,
cached source wrapper, forecast projection, and snapshot carry-forward."""

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

from carbon_mesh.api.deps import _CachedCarbonSource
from carbon_mesh.carbon_sources.snapshot_source import (
    SnapshotBackedSource,
    zone_map_from_intensities,
)
from carbon_mesh.engine.cache import IntensityCache
from carbon_mesh.models.carbon import CarbonIntensity
from carbon_mesh.scheduler.engine import SchedulingEngine

# Load _carry_forward from the snapshot build script (not a package module).
_spec = importlib.util.spec_from_file_location(
    "build_snapshot", Path(__file__).resolve().parent.parent / "scripts" / "build_snapshot.py"
)
build_snapshot = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_snapshot)


def _ci(zone: str, carbon: float, renew: float = 50.0) -> CarbonIntensity:
    return CarbonIntensity(
        grid_zone=zone,
        carbon_intensity_gco2_kwh=carbon,
        renewable_percentage=renew,
        timestamp=datetime.now(timezone.utc),
        source="test",
    )


class _FakeSource:
    """Counts batch calls so we can assert caching/fallback behaviour."""

    def __init__(self, data: dict[str, CarbonIntensity]) -> None:
        self.data = data
        self.batch_calls = 0

    async def get_carbon_intensity(self, zone: str) -> CarbonIntensity:
        return self.data[zone]

    async def get_carbon_intensity_batch(self, zones: list[str]) -> dict[str, CarbonIntensity]:
        self.batch_calls += 1
        return {z: self.data[z] for z in zones if z in self.data}


# --- Snapshot parsing ---


def test_zone_map_from_intensities_dedupes_by_zone():
    intensities = {
        "aws/eu-central-1": {
            "grid_zone": "DE",
            "carbon_intensity_gco2_kwh": 180.0,
            "renewable_percentage": 40.0,
            "timestamp": "2026-06-10T16:00:00+00:00",
            "source": "entsoe",
            "grid_load_mw": 50000,
        },
        "azure/germanywestcentral": {  # same zone -> ignored
            "grid_zone": "DE",
            "carbon_intensity_gco2_kwh": 180.0,
            "renewable_percentage": 40.0,
            "timestamp": "2026-06-10T16:00:00+00:00",
            "source": "entsoe",
        },
        "broken": {"grid_zone": "ZZ"},  # missing fields -> skipped
    }
    zm = zone_map_from_intensities(intensities)
    assert set(zm) == {"DE"}
    assert zm["DE"].carbon_intensity_gco2_kwh == 180.0


# --- Snapshot-backed source: snapshot first, live fallback ---


async def test_snapshot_source_serves_snapshot_then_falls_back(monkeypatch):
    fallback = _FakeSource({"FR": _ci("FR", 55.0)})
    src = SnapshotBackedSource("http://snapshot", fallback)

    async def fake_zone_map():
        return {"DE": _ci("DE", 180.0)}

    monkeypatch.setattr(src, "_zone_map", fake_zone_map)
    res = await src.get_carbon_intensity_batch(["DE", "FR"])
    assert res["DE"].carbon_intensity_gco2_kwh == 180.0  # from snapshot
    assert res["FR"].carbon_intensity_gco2_kwh == 55.0  # from fallback
    assert fallback.batch_calls == 1  # only the missing zone hit the live source


async def test_snapshot_source_empty_url_uses_fallback_only():
    fallback = _FakeSource({"DE": _ci("DE", 180.0)})
    src = SnapshotBackedSource("", fallback)
    res = await src.get_carbon_intensity_batch(["DE"])
    assert res["DE"].carbon_intensity_gco2_kwh == 180.0


# --- Cached source wrapper ---


async def test_cached_source_fetches_once_within_ttl():
    fake = _FakeSource({"DE": _ci("DE", 180.0)})
    cached = _CachedCarbonSource(fake, IntensityCache(ttl_seconds=300))
    await cached.get_carbon_intensity_batch(["DE"])
    await cached.get_carbon_intensity_batch(["DE"])
    assert fake.batch_calls == 1  # second call served from cache


# --- Forecast projection ---


def test_project_with_forecast_scales_by_vre_change():
    engine = SchedulingEngine(carbon_source=_FakeSource({}), grid_mapper=None)
    current = _ci("DE", 300.0, renew=30.0)
    # VRE share rises 30% -> 50%: residual share falls, so carbon falls.
    out = engine._project_with_forecast(current, 0.30, 0.50, 6)
    assert out is not None
    assert out.carbon_intensity_gco2_kwh == round(300.0 * (1 - 0.5) / (1 - 0.3), 2)
    assert out.renewable_percentage == 50.0  # 30 + (0.5-0.3)*100
    # A ~100% VRE zone has no residual to scale -> None (fall back to heuristic).
    assert engine._project_with_forecast(current, 0.999, 0.5, 6) is None


def test_weather_renewable_fraction_from_irradiance_and_wind():
    from carbon_mesh.carbon_sources.open_meteo import weather_renewable_fraction

    assert weather_renewable_fraction(0, 0) == 0.0
    assert weather_renewable_fraction(0, 5) == 0.0  # below wind cut-in
    assert weather_renewable_fraction(1000, 0) == 0.4  # full solar -> 40%
    # Full solar (40%) + strong wind (capped 30%) = 70%.
    assert weather_renewable_fraction(1000, 45) == 0.7


async def test_forecast_zone_uses_weather_source_for_non_eu(monkeypatch):
    class _StubWeather:
        def can_forecast(self, zone: str) -> bool:
            return zone == "SG"

        async def vre_fraction_curve(self, zone: str, hours: int) -> dict[int, float]:
            return {0: 0.1, 3: 0.5}  # cleaner in 3h

    engine = SchedulingEngine(
        carbon_source=_FakeSource({"SG": _ci("SG", 400.0, renew=10.0)}),
        grid_mapper=None,
        forecast_source=None,
        weather_forecast_source=_StubWeather(),
    )
    method, points = await engine.forecast_zone("SG", longitude=103.8, hours=6)
    assert method == "open_meteo_forecast"
    # Hour 3 scaled by the weather VRE rise (0.1 -> 0.5): cleaner than now.
    assert points[3].carbon_intensity_gco2_kwh < points[0].carbon_intensity_gco2_kwh


# --- Snapshot carry-forward ---


def _reading(zone, carbon, quality, ts):
    return {
        "grid_zone": zone,
        "carbon_intensity_gco2_kwh": carbon,
        "renewable_percentage": 50.0,
        "timestamp": ts,
        "source": "entsoe",
        "quality": quality,
        "grid_load_mw": 1000,
    }


def test_carry_forward_replaces_estimate_with_recent_live():
    now = datetime.now(timezone.utc)
    region_meta = {"aws/x": {"provider": "aws", "region": "x"}}
    intensities = {"aws/x": _reading("DE", 200.0, "estimated", now.isoformat())}
    baseline = {
        "intensities": {
            "aws/x": _reading("DE", 180.0, "live", (now - timedelta(hours=2)).isoformat())
        }
    }
    carried = build_snapshot._carry_forward(intensities, region_meta, baseline, 6.0)
    assert carried == 1
    assert intensities["aws/x"]["quality"] == "live"
    assert intensities["aws/x"]["carried_forward"] is True
    assert intensities["aws/x"]["carbon_intensity_gco2_kwh"] == 180.0


def test_carry_forward_skips_stale_and_keeps_fresh_live():
    now = datetime.now(timezone.utc)
    region_meta = {"aws/x": {"provider": "aws", "region": "x"}}
    # Too-old baseline is not carried.
    intensities = {"aws/x": _reading("DE", 200.0, "estimated", now.isoformat())}
    baseline = {
        "intensities": {
            "aws/x": _reading("DE", 180.0, "live", (now - timedelta(hours=12)).isoformat())
        }
    }
    assert build_snapshot._carry_forward(intensities, region_meta, baseline, 6.0) == 0
    assert intensities["aws/x"]["quality"] == "estimated"
    # Fresh live this run is never overwritten.
    intensities = {"aws/x": _reading("DE", 195.0, "live", now.isoformat())}
    build_snapshot._carry_forward(intensities, region_meta, baseline, 6.0)
    assert intensities["aws/x"]["carbon_intensity_gco2_kwh"] == 195.0


def test_append_history_accumulates_and_dedupes():
    snap1 = {
        "generated_at": "2026-06-14T00:00:00+00:00",
        "intensities": {
            "aws/x": {"carbon_intensity_gco2_kwh": 300.0, "renewable_percentage": 40.0}
        },
    }
    snap2 = {
        "generated_at": "2026-06-14T00:30:00+00:00",
        "intensities": {
            "aws/x": {"carbon_intensity_gco2_kwh": 250.0, "renewable_percentage": 55.0}
        },
    }
    h1 = build_snapshot.append_history(None, snap1)
    h2 = build_snapshot.append_history(h1, snap2)
    series = h2["series"]["aws/x"]
    assert [p["c"] for p in series] == [300.0, 250.0]  # oldest first, accumulated
    # Re-running the same snapshot replaces the last point rather than duplicating.
    h3 = build_snapshot.append_history(h2, snap2)
    assert len(h3["series"]["aws/x"]) == 2


def test_history_to_csv_emits_tidy_rows():
    history = {
        "series": {
            "aws/us-east-1": [
                {"t": "2026-06-14T00:00:00+00:00", "c": 300.0, "r": 40.0},
                {"t": "2026-06-14T01:00:00+00:00", "c": 250.0, "r": 55.0},
            ]
        }
    }
    csv_text = build_snapshot.history_to_csv(history)
    lines = csv_text.strip().splitlines()
    assert lines[0] == "provider,region,timestamp,carbon_intensity_gco2_kwh,renewable_percentage"
    assert lines[1] == "aws,us-east-1,2026-06-14T00:00:00+00:00,300.0,40.0"
    assert len(lines) == 3  # header + 2 points


def test_append_history_caps_to_max_points():
    history = None
    for i in range(10):
        snap = {
            "generated_at": f"2026-06-14T{i:02d}:00:00+00:00",
            "intensities": {
                "aws/x": {"carbon_intensity_gco2_kwh": float(i), "renewable_percentage": 0.0}
            },
        }
        history = build_snapshot.append_history(history, snap, max_points=3)
    series = history["series"]["aws/x"]
    assert [p["c"] for p in series] == [7.0, 8.0, 9.0]  # only the newest 3 kept
