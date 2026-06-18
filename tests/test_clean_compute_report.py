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


def test_report_skips_thin_history():
    now = datetime(2026, 6, 16, tzinfo=timezone.utc)
    history = {"series": {"aws/new": [{"t": now.isoformat(), "c": 100.0, "r": 50.0}]}}
    report = build_clean_compute_report(history, {}, now, days=14)
    assert report["most_shiftable"] == []
    assert report["greenest_regions"] == []
