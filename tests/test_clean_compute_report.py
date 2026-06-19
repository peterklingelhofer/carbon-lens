"""Tests for the 'state of clean compute' report builder."""

from datetime import datetime, timedelta, timezone

from carbon_mesh.engine.clean_compute import build_clean_compute_report


def _series(now, clean_c, dirty_c, days=7):
    out = []
    for d in range(days):
        day = now - timedelta(days=d)
        out.append({"t": day.replace(hour=2).isoformat(), "c": clean_c, "r": 80.0})
        out.append({"t": day.replace(hour=18).isoformat(), "c": dirty_c, "r": 10.0})
    return out


def test_report_ranks_shiftability_and_greenness():
    now = datetime(2026, 6, 16, tzinfo=timezone.utc)
    history = {
        "series": {
            "aws/swingy": _series(now, 40, 400),  # big swing, dirty-ish on average
            "gcp/cleanflat": _series(now, 60, 70),  # cleanest on average, tiny swing
        }
    }
    meta = {
        "aws/swingy": {"grid_zone": "US-CAL-CISO", "location": "California"},
        "gcp/cleanflat": {"grid_zone": "FI", "location": "Finland"},
    }
    report = build_clean_compute_report(history, meta, now, days=14)

    # Most-shiftable: the big-swing grid ranks first.
    assert report["most_shiftable"][0]["grid_zone"] == "US-CAL-CISO"
    # Greenest: the low-average region ranks first.
    assert report["greenest_regions"][0]["region"] == "cleanflat"
    assert report["greenest_regions"][0]["typical_gco2_kwh"] == 65.0  # (60 + 70) / 2
    # Each greenest entry carries a within-window trend (cleaner/dirtier).
    assert "trend_pct" in report["greenest_regions"][0]


def test_trend_pct_detects_direction():
    from carbon_mesh.engine.clean_compute import _trend_pct

    # Later half cleaner than earlier half -> negative (greening).
    pts = [
        {"t": "2026-06-10T00:00:00+00:00", "c": 400},
        {"t": "2026-06-11T00:00:00+00:00", "c": 400},
        {"t": "2026-06-12T00:00:00+00:00", "c": 200},
        {"t": "2026-06-13T00:00:00+00:00", "c": 200},
    ]
    assert _trend_pct(pts) == -50.0
    assert _trend_pct(pts[:2]) is None  # too few points


def test_update_clean_compute_history_appends_replaces_and_caps():
    from carbon_mesh.engine.clean_compute import update_clean_compute_history

    report = {
        "greenest_regions": [{"typical_gco2_kwh": 60}, {"typical_gco2_kwh": 80}],
        "most_shiftable": [{"shift_savings_pct": 50}],
    }
    h = update_clean_compute_history(None, report, "2026-06-18")
    assert h["days"][-1] == {
        "date": "2026-06-18",
        "greenest_mean_gco2_kwh": 70.0,
        "top_shiftability_pct": 50,
    }
    # Same day replaces (no duplicate).
    h2 = update_clean_compute_history(
        h, {"greenest_regions": [{"typical_gco2_kwh": 40}], "most_shiftable": []}, "2026-06-18"
    )
    same_day = [d for d in h2["days"] if d["date"] == "2026-06-18"]
    assert len(same_day) == 1 and same_day[0]["greenest_mean_gco2_kwh"] == 40.0
    # Capped to max_points.
    big = {"days": [{"date": f"2026-01-{i:02d}"} for i in range(1, 10)]}
    assert len(update_clean_compute_history(big, report, "2026-06-18", max_points=3)["days"]) == 3


def test_report_skips_thin_history():
    now = datetime(2026, 6, 16, tzinfo=timezone.utc)
    history = {"series": {"aws/new": [{"t": now.isoformat(), "c": 100.0, "r": 50.0}]}}
    report = build_clean_compute_report(history, {}, now, days=14)
    assert report["most_shiftable"] == []
    assert report["greenest_regions"] == []


def test_report_includes_calibration_only_when_it_has_samples():
    now = datetime(2026, 6, 16, tzinfo=timezone.utc)
    history = {"series": {}}

    # Empty / zero-sample calibration -> omitted entirely (no fabricated accuracy).
    none_report = build_clean_compute_report(history, {}, now, calibration={"samples": 0})
    assert "forecast_calibration" not in none_report
    assert "forecast_calibration" not in build_clean_compute_report(history, {}, now)

    cal = {"samples": 3, "calibration_ratio": 0.95, "mean_abs_error_gco2_kwh": 12.0}
    report = build_clean_compute_report(history, {}, now, calibration=cal)
    assert report["forecast_calibration"] == cal
