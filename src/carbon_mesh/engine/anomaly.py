"""Relative-context analysis: is a zone cleaner or dirtier than usual right now?

Compares the current intensity to a baseline drawn from the published history
archive. Pure and side-effect-free so it's unit-testable; mirrors the frontend's
lib/anomaly.ts so the API and the UI agree.
"""

from __future__ import annotations

from datetime import datetime, timezone
from statistics import median

from carbon_mesh.engine.recurring import _parse_utc

_MIN_HOUR_SAMPLES = 3
_MIN_RECENT_SAMPLES = 6
_DEADBAND_PCT = 10.0


def _insufficient(sample_size: int) -> dict:
    return {
        "status": "insufficient_history",
        "basis": "insufficient",
        "baseline_gco2_kwh": None,
        "delta_pct": None,
        "sample_size": sample_size,
    }


def compute_anomaly(current: float, points: list[dict], now: datetime) -> dict:
    """Compare ``current`` to a baseline from history ``points`` (each ``{t,c,r}``).

    Prefers the same hour-of-day (UTC) when there's enough of it; otherwise all
    recent points; otherwise reports insufficient history. ``status`` is
    cleaner_than_usual / typical / dirtier_than_usual within a ±10% deadband.
    """
    target_hour = now.astimezone(timezone.utc).hour
    same_hour: list[float] = []
    all_values: list[float] = []
    for p in points:
        c = p.get("c")
        t = p.get("t")
        if c is None or not t:
            continue
        all_values.append(c)
        ts = _parse_utc(t)
        if ts is None:
            continue
        if ts.hour == target_hour:
            same_hour.append(c)

    if len(same_hour) >= _MIN_HOUR_SAMPLES:
        sample, basis = same_hour, "hour_of_day"
    elif len(all_values) >= _MIN_RECENT_SAMPLES:
        sample, basis = all_values, "recent"
    else:
        return _insufficient(len(all_values))

    baseline = median(sample)
    if baseline <= 0:
        return _insufficient(len(all_values))

    delta_pct = round((current - baseline) / baseline * 100, 1)
    if delta_pct <= -_DEADBAND_PCT:
        status = "cleaner_than_usual"
    elif delta_pct >= _DEADBAND_PCT:
        status = "dirtier_than_usual"
    else:
        status = "typical"
    return {
        "status": status,
        "basis": basis,
        "baseline_gco2_kwh": round(baseline, 1),
        "delta_pct": delta_pct,
        "sample_size": len(sample),
    }
