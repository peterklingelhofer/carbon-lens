"""Emission factors for converting fuel mix (MW) to carbon intensity (gCO2e/kWh).

The factor values no longer live here. They come from the versioned corpus at
``data/emission-factors.json``, which carbon-aware-dispatcher vendors as well, so
the two projects cannot publish different numbers for the same physical quantity
under the same citation. Each record there names the citekey it derives from, the
exact row of the cited table, that row's published range, and the reason for any
deviation. See ``factor_corpus.py`` for the loader and its validation rules.

Basis: lifecycle (incl. upstream/construction) emission factors, predominantly the
medians of IPCC AR5 WG3 (2014) Annex III, Table A.III.2. These are global,
fuel-type lifecycle medians. They are not plant- or region-specific operational factors,
and not US EPA eGRID (eGRID is combustion-only and US-only; we don't use it).

The EIA_FUEL_MAP / GRIDSTATUS_FUEL_MAP below are *name mappings* from each
provider's fuel codes onto these normalized types; they are not a second
source of emission numbers.

Storage (battery, pumped hydro) is excluded from the weighted average rather than
given a factor of zero. Discharge re-delivers energy whose emissions were already
attributed at generation, so counting it again in the denominator dilutes
intensity downward every time storage discharges.
"""

from datetime import datetime

from carbonlens.carbon_sources.factor_corpus import load_corpus
from carbonlens.models.carbon import CarbonIntensity

_CORPUS = load_corpus()

# gCO2eq per kWh, lifecycle. Derived from the corpus; storage keys are absent
# because no factor applies to them.
EMISSION_FACTORS: dict[str, float] = {
    key: factor.value
    for key, factor in _CORPUS.factors.items()
    if factor.value is not None and not factor.storage
}

# Fuel types that store energy instead of generating it: excluded from intensity and
# renewable-percentage maths entirely.
STORAGE_TYPES: frozenset[str] = frozenset(
    key for key, factor in _CORPUS.factors.items() if factor.storage
)

# Fuel types considered renewable (for renewable percentage calculation)
RENEWABLE_TYPES: frozenset[str] = frozenset(
    key for key, factor in _CORPUS.factors.items() if factor.renewable
)

# Fuel types considered carbon-free (renewables + nuclear)
CARBON_FREE_TYPES: frozenset[str] = frozenset(
    key for key, factor in _CORPUS.factors.items() if factor.carbon_free
)

# EIA fuel type codes -> normalized names
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
    "PS": "pumped_storage",
}

# GridStatus fuel column name patterns -> normalized names
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
    "pumped_storage": "pumped_storage",
    "other": "other",
    "other_renewables": "other",
    "multiple_fuels": "other",
    "imports": "other",
}


def _generating_mw(fuel_mix_mw: dict[str, float]) -> dict[str, float]:
    """The mix reduced to actual generation: positive MW, storage removed.

    Storage is dropped rather than zero-weighted so it leaves the denominator
    too; negative entries (storage charging, or a provider netting a bucket) are
    dropped because they are not generation.
    """
    return {fuel: mw for fuel, mw in fuel_mix_mw.items() if mw > 0 and fuel not in STORAGE_TYPES}


def calculate_carbon_intensity(fuel_mix_mw: dict[str, float]) -> float:
    """Weighted-average carbon intensity (gCO2/kWh) from a fuel mix in MW."""
    generating = _generating_mw(fuel_mix_mw)
    total_mw = sum(generating.values())
    if total_mw == 0:
        return 0.0

    weighted_sum = sum(mw * _CORPUS.value(fuel) for fuel, mw in generating.items())
    return weighted_sum / total_mw


# Typical merit order of dispatchable fuels, most-expensive (price-setting) first.
# The marginal unit (what responds to a small change in demand) is usually the
# costliest running fossil (oil peaker, then gas), with coal as marginal only when
# it's the sole fossil. Cost order diverges from carbon order: coal is cheap baseload, gas
# the flexible peaker, so gas (not the dirtier coal) typically sets the margin.
_MARGINAL_MERIT_ORDER = ("petroleum", "oil", "natural_gas", "coal", "biomass")


def calculate_marginal_intensity(fuel_mix_mw: dict[str, float]) -> float:
    """Estimate the marginal emission factor (gCO2/kWh): roughly what an extra kWh
    of demand right now would emit, based on the price-setting generator.

    This is a heuristic from the fuel mix, with no dispatch model and no measured
    marginal data: it takes the emission factor of the most-flexible fossil
    currently generating, or, on an all-clean grid with no fossil running,
    falls back to the average (extra demand met by ramping clean/flexible units).
    """
    generating = _generating_mw(fuel_mix_mw)
    if not generating:
        return 0.0
    for fuel in _MARGINAL_MERIT_ORDER:
        if generating.get(fuel, 0) > 0:
            return _CORPUS.value(fuel)
    return round(calculate_carbon_intensity(fuel_mix_mw), 1)


def calculate_renewable_percentage(fuel_mix_mw: dict[str, float]) -> float:
    """Percentage of generation (0-100) from renewable sources."""
    generating = _generating_mw(fuel_mix_mw)
    total_mw = sum(generating.values())
    if total_mw == 0:
        return 0.0

    renewable_mw = sum(mw for fuel, mw in generating.items() if fuel in RENEWABLE_TYPES)
    return (renewable_mw / total_mw) * 100


def power_breakdown(fuel_mix_mw: dict[str, float]) -> dict[str, float] | None:
    """Normalize a fuel mix into the per-fuel generation breakdown carried on the
    API response. Keeps only fuels actually generating (positive MW), rounded to
    whole MW, so storage charging (negative) and absent fuels drop out. Returns
    None for an empty/non-generating mix so the field stays absent rather than {}.

    Storage that is discharging is kept here (it is real power on the wire and
    callers want to see it), even though it is excluded from the intensity maths.
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

    Raises ValueError when nothing is generating, rather than publishing 0.0.

    This is not a theoretical guard. A weighted average over a mix that sums to
    zero is 0.0 gCO2/kWh, which is indistinguishable from a perfectly clean grid
    and is the *best possible* score a carbon-aware router can see, so a zone
    whose feed has gone hollow does not merely go dark, it wins every routing
    decision. Callers already guarded against an EMPTY mix; they did not guard
    against a mix that is present but all-zero, which is what an upstream feed
    reporting `<quantity>0</quantity>` for every fuel produces. Measured in the
    published archive: three Netherlands regions sat at 0.0 for 23 hours before
    jumping to 460.8. See docs/VALIDATION.md.

    Raising here lets the provider cascade fall through to the next source, which
    is the behaviour the hybrid chain already implements for a failed fetch.
    """
    # Must use the same definition of "generating" the average uses, or a mix of
    # nothing but discharging storage passes the guard and still averages to 0.0.
    if sum(_generating_mw(fuel_mix).values()) <= 0:
        raise ValueError(
            f"{grid_zone}: fuel mix from {source} has no generation; refusing to "
            "publish 0.0 gCO2/kWh, which would read as a perfectly clean grid"
        )
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
