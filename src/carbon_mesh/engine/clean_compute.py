"""Build the public 'state of clean compute' report from the history archive.

A compact, citable artifact published alongside the snapshot: which grids reward
carbon-aware scheduling most (biggest intra-day swing), and which regions are
greenest to host on (lowest typical intensity). Pure function so it's unit-tested;
the script wrapper handles I/O.
"""

from __future__ import annotations

from datetime import datetime, timezone

from carbon_mesh.engine.recurring import mean_intensity, rank_hours_utc, shiftability_pct

_MIN_SAMPLES = 8


def _within(ts: str | None, cutoff: datetime) -> bool:
    if not ts:
        return False
    try:
        t = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return False
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t >= cutoff


def update_clean_compute_history(
    history: dict | None, report: dict, day: str, max_points: int = 84
) -> dict:
    """Append (or replace) one day's summary in the rolling report-history.

    Keeps one point per day so the Clean Compute page can show a real multi-week
    trend. ``day`` is an ISO date (YYYY-MM-DD); capped at ``max_points`` days.
    """
    series = [e for e in (history or {}).get("days", []) if e.get("date") != day]
    greenest = report.get("greenest_regions", [])
    shiftable = report.get("most_shiftable", [])
    series.append(
        {
            "date": day,
            "greenest_mean_gco2_kwh": (
                round(sum(r["typical_gco2_kwh"] for r in greenest) / len(greenest), 1)
                if greenest
                else None
            ),
            "top_shiftability_pct": shiftable[0]["shift_savings_pct"] if shiftable else None,
        }
    )
    series.sort(key=lambda e: e["date"])
    return {"days": series[-max_points:]}


def _trend_pct(points: list[dict]) -> float | None:
    """Within-window trend: later-half mean vs earlier-half mean (%).

    Negative = the grid has been getting cleaner over the window; positive = dirtier.
    A directional read over the available history (about a week), not week-over-week.
    """
    pts = sorted((p for p in points if p.get("c") is not None and p.get("t")), key=lambda p: p["t"])
    if len(pts) < 4:
        return None
    mid = len(pts) // 2
    early = pts[:mid]
    late = pts[mid:]
    early_mean = sum(float(p["c"]) for p in early) / len(early)
    late_mean = sum(float(p["c"]) for p in late) / len(late)
    if early_mean <= 0:
        return None
    return round((late_mean - early_mean) / early_mean * 100, 1)


def build_clean_compute_report(
    history: dict,
    region_meta: dict[str, dict],
    now: datetime,
    days: int = 14,
    top: int = 15,
) -> dict:
    """Rank grids by shiftability and regions by typical intensity from history.

    ``history`` is ``{"series": {"provider/region": [{"t","c","r"}, ...]}}``.
    ``region_meta`` maps that key to ``{"grid_zone", "location"}``.
    """
    from datetime import timedelta

    cutoff = now - timedelta(days=days)
    most_shiftable: list[dict] = []
    greenest: list[dict] = []
    seen_zones: set[str] = set()

    for key, points in history.get("series", {}).items():
        recent = [p for p in points if _within(p.get("t"), cutoff)]
        ranked = rank_hours_utc([{"t": p.get("t"), "c": p.get("c")} for p in recent])
        if sum(r["samples"] for r in ranked) < _MIN_SAMPLES:
            continue
        meta = region_meta.get(key, {})
        provider, _, region = key.partition("/")

        typical = mean_intensity([{"c": p.get("c")} for p in recent])
        if typical is not None:
            greenest.append(
                {
                    "provider": provider,
                    "region": region,
                    "location": meta.get("location", ""),
                    "typical_gco2_kwh": typical,
                    "trend_pct": _trend_pct(recent),
                }
            )

        zone = meta.get("grid_zone", key)
        if zone not in seen_zones:
            pct = shiftability_pct(ranked)
            if pct is not None:
                seen_zones.add(zone)
                most_shiftable.append(
                    {
                        "grid_zone": zone,
                        "location": meta.get("location", ""),
                        "shift_savings_pct": pct,
                        "cleanest_hour_utc": ranked[0]["hour"],
                        "samples": sum(r["samples"] for r in ranked),
                    }
                )

    most_shiftable.sort(key=lambda x: x["shift_savings_pct"], reverse=True)
    greenest.sort(key=lambda x: x["typical_gco2_kwh"])
    return {
        "generated_at": now.isoformat(),
        "days_analyzed": days,
        "most_shiftable": most_shiftable[:top],
        "greenest_regions": greenest[:top],
    }
