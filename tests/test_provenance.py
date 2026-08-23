"""Contract tests for the provenance apparatus.

The point of these is decay resistance. A provenance block that a new provider can
silently skip, or a citekey that can quietly stop resolving, is worse than none: it
looks like evidence and is not. These tests fail the build in both cases.
"""

import json
from datetime import UTC, datetime

import pytest

from carbonlens.carbon_sources import factor_corpus
from carbonlens.carbon_sources.emission_factors import intensity_from_fuel_mix
from carbonlens.compliance.calculator import _data_quality
from carbonlens.models.carbon import CarbonIntensity
from carbonlens.provenance import (
    _REGISTRY,
    all_sources,
    data_quality,
    for_source,
    worst_tier,
)


@pytest.fixture(scope="module")
def citekeys() -> set[str]:
    return {e["id"] for e in json.loads(factor_corpus._CITATIONS_PATH.read_text())}


def _reading(source: str, **kw) -> CarbonIntensity:
    return CarbonIntensity(
        grid_zone="ZZ",
        carbon_intensity_gco2_kwh=200,
        renewable_percentage=30,
        timestamp=datetime.now(UTC),
        source=source,
        **kw,
    )


# ── The apparatus must reach every number ──────────────────────


def test_every_reading_carries_provenance():
    """No construction path may produce an intensity without provenance."""
    for source in all_sources():
        reading = _reading(source)
        assert reading.provenance is not None, source


def test_every_classified_source_cites_something():
    """The rule the handoff asks for: a non-empty citations list on every path."""
    for source in all_sources():
        provenance = _reading(source).provenance
        assert provenance is not None
        assert provenance.citations, f"{source} produces an intensity with no citations"


def test_fuel_mix_readings_carry_provenance():
    """The shared fuel-mix constructor, which most live providers go through."""
    reading = intensity_from_fuel_mix(
        "DE", {"wind": 500, "natural_gas": 500}, "entsoe", datetime.now(UTC)
    )
    assert reading.provenance is not None
    assert reading.provenance.citations
    assert reading.provenance.factors == "ipcc-ar5-wg3-annex3"


def test_an_unclassified_source_is_flagged_not_silently_trusted():
    """A provider added in a hurry must degrade loudly and stay marked unverified."""
    provenance = _reading("brand_new_provider_nobody_classified").provenance
    assert provenance is not None
    assert provenance.evidence_tier == "E"
    assert provenance.citations == []
    assert provenance.caveat and "unverified" in provenance.caveat.lower()


def test_supplied_provenance_is_not_overwritten():
    reading = intensity_from_fuel_mix("DE", {"wind": 1}, "entsoe", datetime.now(UTC))
    kept = reading.provenance
    rebuilt = CarbonIntensity(**reading.model_dump())
    assert rebuilt.provenance == kept


# ── Citekeys must resolve ──────────────────────────────────────


def test_every_provenance_citekey_resolves(citekeys):
    for source, record in _REGISTRY.items():
        for key in record.citations:
            assert key in citekeys, f"{source} cites unknown citekey {key}"
        if record.factors:
            assert record.factors in citekeys, (
                f"{source} names unknown factor table {record.factors}"
            )


def test_registry_keys_match_their_records():
    for key, record in _REGISTRY.items():
        assert record.source == key


# ── Tier arithmetic ────────────────────────────────────────────


def test_worst_tier_is_the_weakest_link():
    assert worst_tier(("A", "A")) == "A"
    assert worst_tier(("A", "D")) == "D"
    assert worst_tier(("B", "E", "A")) == "E"
    assert worst_tier(()) == "E"


def test_estimates_and_mocks_are_tier_e():
    """Anything that is not a real grid reading must be visibly flagged."""
    for source in ("open_meteo", "mock", "eskom_heuristic", "hydro_quebec_heuristic"):
        assert for_source(source).evidence_tier == "E", source


def test_live_grid_operator_feeds_are_tier_a():
    for source in ("eia", "entsoe", "uk_carbon_intensity", "taipower", "ieso"):
        assert for_source(source).evidence_tier == "A", source


# ── Accounting basis: the mixed-basis trap ─────────────────────


def test_uk_is_reported_on_a_different_basis_than_fuel_mix_zones():
    """UK carries NESO's direct factors; fuel-mix zones carry IPCC lifecycle ones.

    If this ever silently becomes equal, either the UK provider changed or someone
    mislabelled it, and cross-zone comparison quietly became wrong in a new way.
    """
    uk = for_source("uk_carbon_intensity")
    de = for_source("entsoe")
    assert uk.accounting_basis == "production_direct"
    assert de.accounting_basis == "production_lifecycle"
    assert uk.accounting_basis != de.accounting_basis
    assert uk.caveat and "ACCOUNTING BASIS" in uk.caveat


def test_flow_tracing_is_consumption_based():
    assert for_source("entsoe_flow_traced").accounting_basis == "consumption_lifecycle"


# ── Assumed factors surface to the caller ──────────────────────


def test_assumed_fuel_in_the_mix_is_flagged():
    """The 'other' bucket has no source; a reading leaning on it must say so."""
    reading = intensity_from_fuel_mix(
        "XX", {"wind": 100, "other": 400}, "entsoe", datetime.now(UTC)
    )
    assert reading.provenance is not None
    assert "other" in reading.provenance.assumed_factors


def test_fully_cited_mix_flags_nothing():
    reading = intensity_from_fuel_mix("XX", {"wind": 100, "coal": 100}, "entsoe", datetime.now(UTC))
    assert reading.provenance is not None
    assert reading.provenance.assumed_factors == []


# ── Data quality is derived from the registry ──────────────────


def test_compliance_data_quality_delegates_to_the_registry():
    for source in all_sources():
        assert _data_quality(source) == data_quality(source)


def test_live_providers_grade_as_measured():
    """Regression: these all graded 'estimated' when a second hardcoded list drifted."""
    for source in ("uk_carbon_intensity", "openelectricity", "taipower", "ieso", "aeso"):
        assert data_quality(source) == "measured", source


def test_heuristics_do_not_grade_as_measured():
    for source in ("eskom_heuristic", "grid_india_heuristic", "ons_brazil_heuristic", "open_meteo"):
        assert data_quality(source) == "modeled", source
    assert data_quality("mock") == "default"


# ── The corpus over the wire ───────────────────────────────────


def test_citations_endpoint_serves_the_whole_corpus(client, citekeys):
    body = client.get("/api/v1/citations").json()
    assert body["total"] == len(citekeys)
    assert {c["id"] for c in body["citations"]} == citekeys
    assert body["corpus_version"]


def test_citations_endpoint_resolves_a_single_key(client):
    body = client.get("/api/v1/citations/ipcc-ar5-wg3-annex3").json()
    assert body["evidence_tier"] == "A"
    assert body["verification"] == "primary-read"
    assert body["backs_claims"]


def test_unknown_citekey_is_404(client):
    assert client.get("/api/v1/citations/not-a-real-key").status_code == 404


def test_citations_can_be_filtered(client):
    tier_e = client.get("/api/v1/citations", params={"evidence_tier": "E"}).json()
    assert tier_e["total"] >= 1
    assert all(c["evidence_tier"] == "E" for c in tier_e["citations"])
    factors = client.get("/api/v1/citations", params={"group": "emission-factors"}).json()
    assert all(c["group"] == "emission-factors" for c in factors["citations"])


def test_a_readings_citekeys_all_resolve_over_the_wire(client):
    """End to end: take a live-shaped reading, follow every citekey it names."""
    reading = intensity_from_fuel_mix(
        "DE", {"wind": 500, "natural_gas": 500}, "entsoe", datetime.now(UTC)
    )
    assert reading.provenance is not None
    assert reading.provenance.citations
    for key in reading.provenance.citations:
        assert client.get(f"/api/v1/citations/{key}").status_code == 200, key


def test_carbon_endpoint_returns_provenance(client):
    body = client.get("/api/v1/carbon/zone/US-CAL-CISO").json()
    assert body["provenance"]["citations"]
    assert body["provenance"]["evidence_tier"] in {"A", "B", "C", "D", "E"}
    assert body["provenance"]["accounting_basis"]


# ── Tier resolution follows the corpus ─────────────────────────


def test_downgrading_a_citekey_downgrades_the_readings_that_cite_it():
    """The drift hole this closes: the tier used to be hardcoded per source, so
    marking a source down in CITATIONS.csl.json left every reading still claiming
    the old tier. Now the tier is resolved from the corpus at read time."""
    import carbonlens.provenance as prov

    assert for_source("entsoe").evidence_tier == "A"
    original = prov._tier_by_citekey
    try:
        downgraded = dict(original())
        downgraded["entsoe-transparency-platform"] = "D"
        prov._tier_by_citekey = lambda: downgraded
        assert for_source("entsoe").evidence_tier == "D"
    finally:
        prov._tier_by_citekey = original


def test_declared_tier_can_only_weaken_never_strengthen():
    """Québec cites IPCC (tier A) but is a fixed guess, so it must stay tier E."""
    quebec = for_source("hydro_quebec_heuristic")
    assert quebec.declared_tier == "E"
    assert quebec.evidence_tier == "E"
    from carbonlens.provenance import citation_tiers

    assert "A" in citation_tiers(quebec.citations)


def test_an_unknown_citekey_counts_as_the_weakest_tier():
    from carbonlens.provenance import citation_tiers

    assert citation_tiers(("no-such-citekey",)) == ("E",)


def test_resolved_tier_matches_the_corpus_for_every_source(citekeys):
    """Every source's tier is the worst of its declared tier and its citations'."""
    from carbonlens.provenance import citation_tiers, worst_tier

    for source, record in _REGISTRY.items():
        expected = worst_tier((record.declared_tier, *citation_tiers(record.citations)))
        assert record.evidence_tier == expected, source
