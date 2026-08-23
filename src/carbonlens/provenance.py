"""Provenance: how each carbon number was produced, and what backs it.

The `source` field on a reading answers "where did this number come from". This
module answers the two harder questions: *why is this the right way to compute it*,
and *who says so*. Every entry names the citekeys behind the number, and citekeys
resolve against ``docs/CITATIONS.csl.json`` (enforced by a test, and unknown keys
are a pyright error via ``CitationId``).

This registry is the single source of truth for source classification. The
compliance calculator's GHG Protocol data-quality grade is derived from it rather
than from a second, separately-maintained list of source names.

One thing worth reading the `accounting_basis` field for. CarbonLens does NOT
report every zone on the same basis:

* Most zones are `production_lifecycle`: a weighted average over the live fuel mix
  using IPCC AR5 lifecycle factors, in which wind is 11 and nuclear is 12.
* UK zones are `production_direct`: NESO publishes its own intensity, computed with
  its own DIRECT combustion factors, in which wind, solar, hydro, nuclear and
  pumped storage are all exactly 0.

A UK number and a German number are therefore not the same quantity, and comparing
them (which `/route` does) flatters whichever zone is reported on the direct basis
at times of high renewable output. The field exists so a caller can see that rather
than discover it. See docs/VERIFICATION.md.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

from carbonlens.carbon_sources.factor_corpus import (
    _CITATIONS_PATH,
    EvidenceTier,
    load_corpus,
)
from carbonlens.citations_generated import CitationId

SourceClass = Literal["live", "modeled", "estimated", "mock"]
AccountingBasis = Literal[
    "production_lifecycle",
    "production_direct",
    "consumption_lifecycle",
    "none",
]

# Worst (highest-letter) tier wins when a number rests on several sources: a chain
# is only as strong as its weakest link.
_TIER_ORDER: dict[EvidenceTier, int] = {"A": 0, "B": 1, "C": 2, "D": 3, "E": 4}

_IPCC_FACTORS: CitationId = "ipcc-ar5-wg3-annex3"

_FUEL_MIX_METHOD = "production-based weighted average over the live fuel mix"


@dataclass(frozen=True)
class SourceProvenance:
    """The published basis for one carbon data source.

    `evidence_tier` is resolved at read time: it is the weakest tier among this
    source's citations in docs/CITATIONS.csl.json, further weakened by
    `declared_tier` where the source is weaker than its citations imply. Marking a
    citekey down in the corpus therefore downgrades every reading that cites it,
    with no second place to remember to edit.
    """

    source: str
    source_class: SourceClass
    accounting_basis: AccountingBasis
    method: str
    factors: CitationId | None
    citations: tuple[CitationId, ...]
    declared_tier: EvidenceTier
    caveat: str | None = None

    @property
    def evidence_tier(self) -> EvidenceTier:
        """Weakest link: the declared tier or any cited source's, whichever is worse."""
        return worst_tier((self.declared_tier, *citation_tiers(self.citations)))


def _p(
    source: str,
    source_class: SourceClass,
    method: str,
    citations: tuple[CitationId, ...],
    tier: EvidenceTier,
    *,
    basis: AccountingBasis = "production_lifecycle",
    factors: CitationId | None = _IPCC_FACTORS,
    caveat: str | None = None,
) -> SourceProvenance:
    return SourceProvenance(
        source=source,
        source_class=source_class,
        accounting_basis=basis,
        method=method,
        factors=factors,
        citations=citations,
        declared_tier=tier,
        caveat=caveat,
    )


# Keyed by the exact `source` string each provider stamps on a reading.
_REGISTRY: dict[str, SourceProvenance] = {
    # ── Live grid-operator feeds, our factors ──
    "eia": _p("eia", "live", _FUEL_MIX_METHOD, ("eia-hourly-grid-monitor", _IPCC_FACTORS), "A"),
    "entsoe": _p(
        "entsoe", "live", _FUEL_MIX_METHOD, ("entsoe-transparency-platform", _IPCC_FACTORS), "A"
    ),
    "openelectricity": _p(
        "openelectricity", "live", _FUEL_MIX_METHOD, ("openelectricity-api", _IPCC_FACTORS), "A"
    ),
    "ieso": _p("ieso", "live", _FUEL_MIX_METHOD, ("ieso-data-directory", _IPCC_FACTORS), "A"),
    "aeso": _p(
        "aeso", "live", _FUEL_MIX_METHOD, ("aeso-current-supply-demand", _IPCC_FACTORS), "A"
    ),
    "taipower": _p(
        "taipower", "live", _FUEL_MIX_METHOD, ("taipower-generation-data", _IPCC_FACTORS), "A"
    ),
    "ons_brazil": _p(
        "ons_brazil",
        "live",
        _FUEL_MIX_METHOD,
        ("ons-brazil-open-data", _IPCC_FACTORS),
        "A",
        caveat=(
            "Brazil is hydro-dominated and the single hydro median (24) hides a published "
            "range up to 2200 for reservoir hydro in warm climates. This zone's uncertainty "
            "is far wider than the point estimate suggests."
        ),
    ),
    "grid_india": _p(
        "grid_india",
        "live",
        _FUEL_MIX_METHOD,
        ("grid-india-reports", _IPCC_FACTORS),
        "C",
        caveat="The upstream endpoint could not be verified from this project; see the citekey's caveat.",
    ),
    "gridstatus": _p(
        "gridstatus",
        "live",
        _FUEL_MIX_METHOD,
        ("gridstatus-io", _IPCC_FACTORS),
        "C",
        caveat="Commercial aggregator whose endpoint could not be verified from this project.",
    ),
    # ── Live feeds that publish their own intensity ──
    "uk_carbon_intensity": _p(
        "uk_carbon_intensity",
        "live",
        "NESO's own published carbon intensity for the zone (this project does not compute it)",
        ("neso-carbon-intensity-api", "neso-carbon-intensity-methodology"),
        "A",
        basis="production_direct",
        factors="neso-carbon-intensity-methodology",
        caveat=(
            "DIFFERENT ACCOUNTING BASIS to every fuel-mix zone. NESO's factors are direct "
            "combustion, scoring wind, solar, hydro, nuclear and pumped storage at exactly 0, "
            "where this project's IPCC lifecycle factors score them 11, 48, 24, 12 and n/a. "
            "A UK number is therefore not directly comparable with a fuel-mix zone's number, "
            "and the gap widens as UK renewable output rises. Renewable percentage for UK "
            "zones is additionally inferred from the intensity; NESO doesn't report it."
        ),
    ),
    "electricity_maps": _p(
        "electricity_maps",
        "live",
        "Electricity Maps' own published intensity for the zone",
        ("electricity-maps-api", "electricity-maps-default-factors"),
        "D",
        factors="electricity-maps-default-factors",
        caveat=(
            "Commercial and not independently auditable. Their default factor table differs "
            "from this project's corpus: notably solar 45 (an average of the AR5 rooftop and "
            "utility rows rather than either one) and battery discharge at world-average "
            "intensity rather than excluded."
        ),
    ),
    # ── Consumption-based ──
    "entsoe_flow_traced": _p(
        "entsoe_flow_traced",
        "live",
        "consumption-based intensity via flow tracing over the interconnected network",
        (
            "tranberg-2019-flow-tracing",
            "bialek-1996-tracing-electricity",
            "entsoe-transparency-platform",
            _IPCC_FACTORS,
        ),
        "B",
        basis="consumption_lifecycle",
        caveat=(
            "Rests on the proportional-sharing assumption: a zone's exports are assumed to "
            "carry its whole consumed mix. Only the traced European subnetwork is modelled, "
            "so flows in from outside it are attributed to the 'other' bucket."
        ),
    ),
    # ── Estimates and models: no source licenses these as carbon measurements ──
    "open_meteo": _p(
        "open_meteo",
        "estimated",
        "renewable potential inferred from live irradiance and wind speed, then mapped to an intensity",
        ("open-meteo-api",),
        "E",
        basis="none",
        factors=None,
        caveat=(
            "NOT A CARBON MEASUREMENT. The weather data is real; the mapping from irradiance "
            "and wind speed to a grid carbon intensity is this project's own construction and "
            "no published source supports it. Demo coverage for zones with no grid feed."
        ),
    ),
    "eskom_heuristic": _p(
        "eskom_heuristic",
        "modeled",
        "fixed time-of-day curve around an assumed ~780 gCO2/kWh coal-dominated base",
        ("eskom-data-portal",),
        "E",
        basis="none",
        factors=None,
        caveat=(
            "ASSUMED. Neither the 780 base nor the shape of the time-of-day curve (the 0.92 "
            "midday and 1.02 night multipliers) comes from any source. Eskom publishes no free "
            "real-time fuel mix, so this is illustrative only."
        ),
    ),
    "grid_india_heuristic": _p(
        "grid_india_heuristic",
        "modeled",
        "per-region fallback estimate with a time-of-day adjustment, used when the live feed fails",
        ("grid-india-reports",),
        "E",
        basis="none",
        factors=None,
        caveat="ASSUMED. The fallback baseline and the curve shape have no published source.",
    ),
    "ons_brazil_heuristic": _p(
        "ons_brazil_heuristic",
        "modeled",
        "per-region fallback estimate, used when the live ONS feed fails",
        ("ons-brazil-open-data",),
        "E",
        basis="none",
        factors=None,
        caveat="ASSUMED. The fallback baseline has no published source.",
    ),
    "hydro_quebec_heuristic": _p(
        "hydro_quebec_heuristic",
        "modeled",
        "fixed estimate of 30 gCO2/kWh for a ~99% hydro/wind grid",
        (_IPCC_FACTORS,),
        "E",
        basis="none",
        factors=None,
        caveat=(
            "ASSUMED. Hydro-Québec publishes no free real-time fuel feed. The 30 is a fixed "
            "guess with no reading behind it, and it never changes hour to hour."
        ),
    ),
    "mock": _p(
        "mock",
        "mock",
        "static demo fixture, returned only when every real source fails for a zone",
        (_IPCC_FACTORS,),
        "E",
        basis="none",
        factors=None,
        caveat="NOT REAL DATA. A labelled fixture so the API always returns something.",
    ),
}

# What an unrecognised source string gets. Deliberately the worst tier: a source
# nobody has classified is not a source anybody has checked.
_UNKNOWN = _p(
    "unknown",
    "estimated",
    "unclassified source",
    (),
    "E",
    basis="none",
    factors=None,
    caveat="This source has no provenance record. Treat the number as unverified.",
)


def for_source(source: str) -> SourceProvenance:
    """Provenance for a reading's `source` string.

    A snapshot carries forward the originating source's own string, so snapshot
    reads resolve to the provider that actually produced the number. A source
    with no record resolves to an explicitly unverified record rather than to
    silence.
    """
    known = _REGISTRY.get(source)
    if known is not None:
        return known
    # The snapshot builder may prefix or suffix; fall back to a prefix match before
    # giving up, so a carried-forward reading is not downgraded to unknown.
    for key, value in _REGISTRY.items():
        if source.startswith(key):
            return value
    return SourceProvenance(
        source=source,
        source_class=_UNKNOWN.source_class,
        accounting_basis=_UNKNOWN.accounting_basis,
        method=_UNKNOWN.method,
        factors=None,
        citations=(),
        declared_tier="E",
        caveat=_UNKNOWN.caveat,
    )


@lru_cache(maxsize=1)
def _tier_by_citekey() -> dict[str, EvidenceTier]:
    """Evidence tier of every citekey, read from the CSL-JSON corpus."""
    entries = json.loads(_CITATIONS_PATH.read_text(encoding="utf-8"))
    return {e["id"]: (e.get("custom") or {}).get("evidenceTier", "E") for e in entries}


def citation_tiers(citations: tuple[CitationId, ...]) -> tuple[EvidenceTier, ...]:
    """Tiers of the given citekeys. An unknown key still yields a tier of E."""
    lookup = _tier_by_citekey()
    return tuple(lookup.get(key, "E") for key in citations)


def worst_tier(tiers: tuple[EvidenceTier, ...]) -> EvidenceTier:
    """The weakest tier in a chain; 'A' for an empty chain is never returned."""
    if not tiers:
        return "E"
    return max(tiers, key=lambda t: _TIER_ORDER[t])


@lru_cache(maxsize=1)
def assumed_factor_keys() -> tuple[str, ...]:
    """Fuel keys whose emission factor is an assumption rather than a citation.

    A reading whose fuel mix contains one of these leans on an unsourced number,
    and the provenance block says so.
    """
    return tuple(sorted(key for key, factor in load_corpus().factors.items() if factor.is_assumed))


# GHG Protocol data-quality grade per source class. Derived from the registry so it
# cannot drift from the source classification the way a separate hardcoded list did.
_QUALITY_BY_CLASS: dict[SourceClass, str] = {
    "live": "measured",
    "modeled": "modeled",
    "estimated": "modeled",
    "mock": "default",
}


def data_quality(source: str) -> str:
    """GHG Protocol data-quality grade for a reading's source."""
    return _QUALITY_BY_CLASS[for_source(source).source_class]


def all_sources() -> tuple[str, ...]:
    """Every classified source string, for tests and the methodology endpoint."""
    return tuple(sorted(_REGISTRY))
