"""Recommend the greenest hour-of-day to run a *recurring* job.

Most cron jobs (backups, nightly ETL, reports, CI) run at an arbitrary hour picked
by habit. Moving that fixed schedule to the statistically-cleanest hour is a
one-time change with permanent, zero-friction savings. This ranks hours by their
mean carbon intensity, from the rolling history archive when we have it, or the
forecast curve as a fallback -- a pure function so it's easy to test.
"""

from __future__ import annotations

from datetime import datetime


def rank_hours_utc(points: list[dict]) -> list[dict]:
    """Mean carbon intensity by UTC hour-of-day across history-style points.

    Each point is ``{"t": iso8601, "c": gco2_kwh}``. Returns hours sorted
    cleanest-first: ``[{"hour": 0-23, "mean_gco2_kwh": float, "samples": int}]``.
    Hours with no data are simply absent.
    """
    buckets: dict[int, list[float]] = {}
    for p in points:
        t, c = p.get("t"), p.get("c")
        if t is None or c is None:
            continue
        try:
            hour = datetime.fromisoformat(t).hour
        except (TypeError, ValueError):
            continue
        buckets.setdefault(hour, []).append(float(c))

    ranked = [
        {"hour": h, "mean_gco2_kwh": round(sum(vals) / len(vals), 1), "samples": len(vals)}
        for h, vals in buckets.items()
    ]
    ranked.sort(key=lambda r: (r["mean_gco2_kwh"], r["hour"]))
    return ranked


def mean_intensity(points: list[dict]) -> float | None:
    """Mean carbon intensity across history points (each ``{"c": gco2_kwh, ...}``).

    The 'typical' intensity of a grid -- the honest basis for a permanent 24/7
    siting decision, unlike the instantaneous value used for per-request routing.
    """
    vals = [float(p["c"]) for p in points if p.get("c") is not None]
    return round(sum(vals) / len(vals), 1) if vals else None


def shiftability_pct(ranked: list[dict]) -> float | None:
    """How much a daily job would save by moving from the worst to the best hour (%).

    A grid's 'shiftability': high where intensity swings a lot through the day (so
    carbon-aware scheduling pays off), near zero on flat grids (always-clean hydro/
    nuclear, or always-dirty) where it barely helps. ``ranked`` is rank_hours_utc output.
    """
    if not ranked:
        return None
    best = ranked[0]["mean_gco2_kwh"]
    worst = ranked[-1]["mean_gco2_kwh"]
    if worst <= 0:
        return None
    return round((worst - best) / worst * 100, 1)
