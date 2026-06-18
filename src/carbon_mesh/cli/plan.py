"""Pure annual carbon-opportunity calculator for `carbonlens plan`.

Synthesises the two levers into one decision number: for a continuous workload, the
estimated annual CO2 if you deploy carbon-blind vs. carbon-aware -- pick the greenest
region (spatial) and shift the flexible fraction into clean hours (temporal). Built on
the /carbon/siting and /carbon/shiftability responses; kept pure so it's unit-tested.
"""

from __future__ import annotations

_HOURS_PER_YEAR = 8760


def plan_estimate(
    siting: dict, shiftability: dict, power_watts: float, flexible_fraction: float
) -> dict:
    """Annual kg CO2 naive vs optimized for a continuous ``power_watts`` workload.

    ``flexible_fraction`` (0-1) is how much of the load can be time-shifted. Naive =
    a carbon-blind region pick (mean of candidates); optimized = the greenest region,
    then the flexible share shifted by that region's shiftability. An estimate that
    assumes today's grid patterns hold.
    """
    options = siting.get("options", [])
    if not options:
        return {"available": False}

    power_kw = power_watts / 1000
    typicals = [o["typical_gco2_kwh"] for o in options]
    best = options[0]
    naive_typical = sum(typicals) / len(typicals)
    best_typical = best["typical_gco2_kwh"]

    def annual_kg(intensity: float) -> float:
        return intensity * power_kw * _HOURS_PER_YEAR / 1000

    naive_kg = annual_kg(naive_typical)
    after_region_kg = annual_kg(best_typical)
    region_saving = naive_kg - after_region_kg

    # Shiftability of the chosen region's grid zone (0 if we have no read for it).
    pct = 0.0
    for z in shiftability.get("zones", []):
        if z.get("grid_zone") == best.get("grid_zone"):
            pct = z.get("shift_savings_pct", 0.0) or 0.0
            break
    flexible_kwh = power_kw * _HOURS_PER_YEAR * max(0.0, min(1.0, flexible_fraction))
    shift_saving = best_typical * flexible_kwh * (pct / 100) / 1000

    optimized_kg = max(0.0, after_region_kg - shift_saving)
    return {
        "available": True,
        "best_region": f"{best['provider']}/{best['region']}",
        "best_grid_zone": best.get("grid_zone"),
        "shiftability_pct": round(pct, 1),
        "naive_annual_kg": round(naive_kg, 1),
        "optimized_annual_kg": round(optimized_kg, 1),
        "region_saving_kg": round(region_saving, 1),
        "shift_saving_kg": round(shift_saving, 1),
        "total_saving_kg": round(naive_kg - optimized_kg, 1),
    }
