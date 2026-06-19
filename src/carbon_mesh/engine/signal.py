"""The run-now/wait decision signal -- the single source of truth.

Both the live API (``/carbon/signal/...``) and the static snapshot builder call
``build_signal`` so the precomputed CDN signal is byte-for-byte the same decision the
API would return. Kept free of FastAPI so the snapshot script can import it without
pulling in the web layer.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from carbon_mesh.engine.surplus import is_clean_surplus, surplus_offsets
from carbon_mesh.models.carbon import CarbonSignal

if TYPE_CHECKING:
    from carbon_mesh.carbon_sources.base import CarbonDataSource
    from carbon_mesh.carbon_sources.marginal import MarginalSource
    from carbon_mesh.scheduler.engine import SchedulingEngine


def signal_state(intensity: float) -> str:
    """green | yellow | red, by absolute intensity thresholds."""
    if intensity <= 150:
        return "green"
    if intensity <= 400:
        return "yellow"
    return "red"


def marginal_note(avg: float, marginal: float | None) -> str | None:
    """An honest caveat when the marginal picture changes the run-now/wait call.

    Marginal -- what an extra kWh emits right now -- is what actually responds to
    shifting load, not the average. When a grid is clean on average but fossil on the
    margin, shifting helps more than the average implies; when the margin is already
    clean, it helps little. Returns None when nothing notable applies."""
    if marginal is None:
        return None
    if marginal >= 300 and marginal >= avg * 1.3:
        return (
            f"Clean on average, but extra load here is met mostly by fossil generation "
            f"(~{round(marginal)} gCO₂/kWh on the margin), so shifting time or region cuts "
            f"more than the average suggests."
        )
    if marginal <= 100:
        return "Clean even on the margin: extra demand is largely served by low-carbon power."
    return None


async def build_signal(
    provider: str,
    region: str,
    zone: str,
    longitude: float,
    engine: SchedulingEngine,
    source: CarbonDataSource,
    marginal_source: MarginalSource | None = None,
) -> CarbonSignal:
    """Core run-now/wait decision for a grid zone. Shared by the cloud-region and
    on-prem (zone) endpoints and the snapshot builder so all make the exact same
    marginal/surplus-aware call."""
    _, points = await engine.forecast_zone(zone, longitude, 24)
    intensities = [p.carbon_intensity_gco2_kwh for p in points]
    now_v = intensities[0]
    state = signal_state(now_v)

    # Soonest upcoming hour that's notably cleaner (>= 15% lower) than now.
    best_i, best_v = 0, now_v
    for i in range(1, len(intensities)):
        if intensities[i] < best_v:
            best_i, best_v = i, intensities[i]
    notably_cleaner = best_i >= 1 and best_v <= now_v * 0.85

    # Marginal is what actually responds to shifting load, so surface it (and an
    # honest caveat) alongside the average-based traffic light. Clean surplus is the
    # strongest run-now case: renewables abundant, so extra load soaks up would-be
    # curtailed power.
    current = await source.get_carbon_intensity(zone)
    marginal = current.marginal_intensity_gco2_kwh
    marginal_basis = "heuristic"
    # If the operator configured a measured-marginal source for this zone, prefer it.
    if marginal_source is not None and marginal_source.can_handle(zone):
        measured = await marginal_source.marginal_intensity(zone)
        if measured is not None:
            marginal, marginal_basis = measured, "measured"
    surplus = is_clean_surplus(current.renewable_percentage, now_v, marginal)

    # Soonest upcoming clean-surplus window (the highest-value time to shift into).
    surplus_window = next((h for h in surplus_offsets(points) if h >= 1), None)

    if surplus:
        advice, window_h, window_v = "run_now", None, None
        note = (
            "Renewables are abundant right now (likely surplus): extra load is largely served "
            "by clean power that might otherwise be curtailed. Ideal time to run flexible jobs."
        )
    elif surplus_window is not None:
        advice, window_h, window_v = (
            "wait_for_cleaner",
            surplus_window,
            round(intensities[surplus_window]),
        )
        note = (
            f"A clean-surplus window (renewables abundant) is expected in ~{surplus_window}h -- "
            f"the highest-value time to run a flexible job."
        )
    elif state == "green" or not notably_cleaner:
        advice, window_h, window_v = "run_now", None, None
        note = marginal_note(now_v, marginal)
    else:
        advice, window_h, window_v = "wait_for_cleaner", best_i, round(best_v)
        note = marginal_note(now_v, marginal)

    return CarbonSignal(
        provider=provider,
        region=region,
        grid_zone=zone,
        intensity_gco2_kwh=round(now_v),
        state=state,
        advice=advice,
        marginal_intensity_gco2_kwh=marginal,
        marginal_note=note,
        marginal_basis=marginal_basis,
        clean_surplus=surplus,
        surplus_window_in_hours=surplus_window,
        cleaner_window_in_hours=window_h,
        cleaner_window_intensity_gco2_kwh=window_v,
    )
