"""Emission factors for converting fuel mix (MW) to carbon intensity (gCO2e/kWh).

Basis: lifecycle (incl. upstream/construction) median emission factors from the
IPCC AR5 WG3 (2014), Annex III, Table A.III.2. A couple of values deliberately
deviate from the IPCC median and are noted inline where they do, so the choice
is transparent rather than implied. These are global, fuel-type lifecycle medians
-- not plant- or region-specific operational factors, and not US EPA eGRID
(eGRID is combustion-only and US-only; we don't use it for the factor values).

The EIA_FUEL_MAP / GRIDSTATUS_FUEL_MAP below are *name mappings* from each
provider's fuel codes onto these normalized types -- they are not a second
source of emission numbers.
"""

from datetime import datetime

from carbon_mesh.models.carbon import CarbonIntensity

# gCO2e per kWh, lifecycle (IPCC AR5 2014 medians unless a note says otherwise)
EMISSION_FACTORS: dict[str, float] = {
    # Fossil fuels
    "coal": 900,  # conservative; IPCC median is 820, but subcritical/lignite runs higher
    "natural_gas": 430,  # efficient CCGT end; IPCC median is 490 (higher w/ methane leakage)
    "oil": 650,  # no IPCC median row; mid-range diesel/HFO lifecycle estimate
    "petroleum": 650,
    # Low-carbon (IPCC AR5 medians)
    "nuclear": 12,
    "hydro": 24,  # median; reservoir hydro can be far higher due to methane -- single value hides this
    "wind": 11,
    "solar": 41,  # utility PV median
    "geothermal": 38,
    "biomass": 230,  # operational median; biogenic-CO2 accounting is contested
    "battery": 0,  # storage -- discharge emissions belong to the charging source, not zero in reality
    "other": 300,  # conservative placeholder for unknown/mixed fuels
}

# Fuel types considered renewable (for renewable percentage calculation)
RENEWABLE_TYPES = {"wind", "solar", "hydro", "geothermal"}

# Fuel types considered carbon-free (renewables + nuclear)
CARBON_FREE_TYPES = RENEWABLE_TYPES | {"nuclear", "battery"}

# EIA fuel type codes → normalized names
EIA_FUEL_MAP: dict[str, str] = {
    "COL": "coal",
    "NG": "natural_gas",
    "NUC": "nuclear",
    "WND": "wind",
    "SUN": "solar",
    "WAT": "hydro",
    "OIL": "petroleum",
    "GEO": "geothermal",
    "OTH": "other",
    "BAT": "battery",
}

# GridStatus fuel column name patterns → normalized names
# Each ISO uses slightly different column names
GRIDSTATUS_FUEL_MAP: dict[str, str] = {
    "coal": "coal",
    "coal_and_lignite": "coal",
    "gas": "natural_gas",
    "natural_gas": "natural_gas",
    "nuclear": "nuclear",
    "wind": "wind",
    "solar": "solar",
    "hydro": "hydro",
    "large_hydro": "hydro",
    "hydroelectric": "hydro",
    "geothermal": "geothermal",
    "oil": "petroleum",
    "petroleum": "petroleum",
    "biomass": "biomass",
    "batteries": "battery",
    "battery": "battery",
    "power_storage": "battery",
    "storage": "battery",
    "other": "other",
    "other_renewables": "other",
    "multiple_fuels": "other",
    "imports": "other",
}


def calculate_carbon_intensity(fuel_mix_mw: dict[str, float]) -> float:
    """Weighted-average carbon intensity (gCO2/kWh) from a fuel mix in MW."""
    total_mw = sum(max(0, v) for v in fuel_mix_mw.values())
    if total_mw == 0:
        return 0.0

    weighted_sum = 0.0
    for fuel, mw in fuel_mix_mw.items():
        if mw <= 0:
            continue
        factor = EMISSION_FACTORS.get(fuel, EMISSION_FACTORS["other"])
        weighted_sum += mw * factor

    return weighted_sum / total_mw


# Typical merit order of dispatchable fuels, most-expensive (price-setting) first.
# The marginal unit -- what responds to a small change in demand -- is usually the
# costliest running fossil (oil peaker, then gas), with coal as marginal only when
# it's the sole fossil. Cost order, not carbon order: coal is cheap baseload, gas
# the flexible peaker, so gas (not the dirtier coal) typically sets the margin.
_MARGINAL_MERIT_ORDER = ("petroleum", "oil", "natural_gas", "coal", "biomass")


def calculate_marginal_intensity(fuel_mix_mw: dict[str, float]) -> float:
    """Estimate the marginal emission factor (gCO2/kWh): roughly what an extra kWh
    of demand right now would emit, based on the price-setting generator.

    This is a heuristic from the fuel mix, NOT a dispatch model or measured
    marginal data: it takes the emission factor of the most-flexible fossil
    currently generating, or -- on an all-clean grid with no fossil running --
    falls back to the average (extra demand met by ramping clean/flexible units).
    """
    if not fuel_mix_mw or sum(max(0, v) for v in fuel_mix_mw.values()) == 0:
        return 0.0
    for fuel in _MARGINAL_MERIT_ORDER:
        if fuel_mix_mw.get(fuel, 0) > 0:
            return float(EMISSION_FACTORS.get(fuel, EMISSION_FACTORS["other"]))
    return round(calculate_carbon_intensity(fuel_mix_mw), 1)


def calculate_renewable_percentage(fuel_mix_mw: dict[str, float]) -> float:
    """Percentage of generation (0-100) from renewable sources."""
    total_mw = sum(max(0, v) for v in fuel_mix_mw.values())
    if total_mw == 0:
        return 0.0

    renewable_mw = sum(max(0, fuel_mix_mw.get(f, 0)) for f in RENEWABLE_TYPES)
    return (renewable_mw / total_mw) * 100


def power_breakdown(fuel_mix_mw: dict[str, float]) -> dict[str, float] | None:
    """Normalize a fuel mix into the per-fuel generation breakdown carried on the
    API response. Keeps only fuels actually generating (positive MW), rounded to
    whole MW, so storage charging (negative) and absent fuels drop out. Returns
    None for an empty/non-generating mix so the field stays absent rather than {}.
    """
    breakdown = {fuel: float(round(mw)) for fuel, mw in fuel_mix_mw.items() if mw > 0}
    return breakdown or None


def intensity_from_fuel_mix(
    grid_zone: str,
    fuel_mix: dict[str, float],
    source: str,
    timestamp: datetime,
) -> CarbonIntensity:
    """Build a full CarbonIntensity from a fuel mix (MW), running the average,
    renewable, marginal, and per-fuel breakdown calcs in one place so the fuel-mix
    adapters (AEMO, Canada, ENTSO-E, EIA, Taiwan) stay in sync.
    """
    return CarbonIntensity(
        grid_zone=grid_zone,
        carbon_intensity_gco2_kwh=round(calculate_carbon_intensity(fuel_mix), 1),
        renewable_percentage=round(calculate_renewable_percentage(fuel_mix), 1),
        timestamp=timestamp,
        source=source,
        grid_load_mw=round(sum(fuel_mix.values())),
        marginal_intensity_gco2_kwh=round(calculate_marginal_intensity(fuel_mix), 1),
        power_breakdown_mw=power_breakdown(fuel_mix),
    )
