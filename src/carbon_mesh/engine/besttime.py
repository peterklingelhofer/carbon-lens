"""The greenest-hour-of-day ranking -- shared by the live API and the snapshot builder.

Pure: the caller supplies the history series (and a forecast curve for the fallback when
history is too thin), so the static snapshot can precompute the exact same BestTime the
``/carbon/best-time`` endpoint returns.
"""

from __future__ import annotations

from carbon_mesh.engine.recurring import rank_hours_utc
from carbon_mesh.models.carbon import BestTime, HourRank

# Minimum hourly observations before we trust history over the forecast-curve fallback.
_MIN_HISTORY_SAMPLES = 8


def build_best_time(
    provider: str,
    region: str,
    zone: str,
    raw_series: list[dict],
    forecast_points: list[dict] | None,
    days: int,
    energy_kwh: float | None = None,
) -> BestTime:
    """Rank UTC hours by mean carbon intensity from ``raw_series`` (``[{"t","c"}, ...]``).

    Falls back to ranking ``forecast_points`` (same shape) when history is too thin,
    labelling ``basis`` accordingly. Moving a fixed daily job to ``cleanest_hour_utc`` is
    a one-time change with permanent savings."""
    ranked = rank_hours_utc(raw_series)
    basis = "history"
    if sum(r["samples"] for r in ranked) < _MIN_HISTORY_SAMPLES:
        forecast_ranked = rank_hours_utc(forecast_points or [])
        if forecast_ranked:
            ranked, basis = forecast_ranked, "forecast"
        elif not ranked:
            basis = "insufficient"

    cleanest = ranked[0]["hour"] if ranked else None
    dirtiest = ranked[-1]["hour"] if ranked else None
    shift_savings_pct = None
    annual_kg_saved = None
    if ranked:
        best_mean = ranked[0]["mean_gco2_kwh"]
        worst_mean = ranked[-1]["mean_gco2_kwh"]
        if worst_mean > 0:
            shift_savings_pct = round((worst_mean - best_mean) / worst_mean * 100, 1)
        if energy_kwh:
            # gCO2/kWh delta x kWh/day x 365 days, to kg.
            annual_kg_saved = round((worst_mean - best_mean) * energy_kwh * 365 / 1000, 1)

    return BestTime(
        provider=provider,
        region=region,
        grid_zone=zone,
        basis=basis,
        days_analyzed=days,
        cleanest_hour_utc=cleanest,
        dirtiest_hour_utc=dirtiest,
        shift_savings_pct=shift_savings_pct,
        annual_kg_saved=annual_kg_saved,
        suggested_cron=f"0 {cleanest} * * *" if cleanest is not None else None,
        ranked_hours=[
            HourRank(hour_utc=r["hour"], mean_gco2_kwh=r["mean_gco2_kwh"], samples=r["samples"])
            for r in ranked[:6]
        ],
    )
