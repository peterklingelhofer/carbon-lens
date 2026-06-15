"""Unit tests for the cleaner/dirtier-than-usual baseline computation."""

from datetime import datetime, timezone

from carbon_mesh.engine.anomaly import compute_anomaly

NOW = datetime(2026, 6, 20, 14, tzinfo=timezone.utc)  # UTC hour 14


def _points(hour: int, values: list[float]) -> list[dict]:
    return [
        {"t": f"2026-06-{10 + i:02d}T{hour:02d}:00:00+00:00", "c": v, "r": 50.0}
        for i, v in enumerate(values)
    ]


def test_insufficient_history():
    result = compute_anomaly(100, _points(14, [100, 110]), NOW)
    assert result["status"] == "insufficient_history"
    assert result["baseline_gco2_kwh"] is None


def test_cleaner_against_hour_of_day_baseline():
    result = compute_anomaly(200, _points(14, [380, 400, 420]), NOW)
    assert result["basis"] == "hour_of_day"
    assert result["status"] == "cleaner_than_usual"
    assert result["delta_pct"] == -50.0  # (200-400)/400
    assert result["baseline_gco2_kwh"] == 400.0


def test_dirtier_than_usual():
    result = compute_anomaly(300, _points(14, [180, 200, 220]), NOW)
    assert result["status"] == "dirtier_than_usual"


def test_typical_within_deadband():
    result = compute_anomaly(205, _points(14, [190, 200, 210]), NOW)
    assert result["status"] == "typical"


def test_falls_back_to_recent_when_hour_is_thin():
    result = compute_anomaly(100, _points(9, [300, 300, 300, 300, 300, 300]), NOW)
    assert result["basis"] == "recent"
    assert result["status"] == "cleaner_than_usual"
