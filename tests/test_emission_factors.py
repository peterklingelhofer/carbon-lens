import json

import pytest

from carbonlens.carbon_sources import factor_corpus
from carbonlens.carbon_sources.emission_factors import (
    EMISSION_FACTORS,
    STORAGE_TYPES,
    calculate_carbon_intensity,
    calculate_marginal_intensity,
    calculate_renewable_percentage,
    power_breakdown,
)
from carbonlens.carbon_sources.factor_corpus import FactorCorpusError, load_corpus


def test_pure_wind():
    mix = {"wind": 1000}
    assert calculate_carbon_intensity(mix) == 11.0
    assert calculate_renewable_percentage(mix) == 100.0


def test_pure_coal():
    mix = {"coal": 1000}
    assert calculate_carbon_intensity(mix) == 820.0
    assert calculate_renewable_percentage(mix) == 0.0


def test_mixed_grid():
    mix = {"wind": 500, "natural_gas": 500}
    intensity = calculate_carbon_intensity(mix)
    # (500*11 + 500*490) / 1000 = 250.5
    assert abs(intensity - 250.5) < 0.1
    assert calculate_renewable_percentage(mix) == 50.0


def test_empty_mix():
    assert calculate_carbon_intensity({}) == 0.0
    assert calculate_renewable_percentage({}) == 0.0


def test_negative_values_ignored():
    # Storage charging shows as negative MW and is not generation.
    mix = {"solar": 500, "battery": -100, "natural_gas": 200}
    total_positive = 500 + 200
    renewable_pct = calculate_renewable_percentage(mix)
    assert abs(renewable_pct - (500 / total_positive * 100)) < 0.1


def test_all_renewable_types():
    mix = {"wind": 100, "solar": 100, "hydro": 100, "geothermal": 100}
    assert calculate_renewable_percentage(mix) == 100.0


def test_nuclear_not_renewable():
    mix = {"nuclear": 1000}
    assert calculate_renewable_percentage(mix) == 0.0
    # But very low carbon
    assert calculate_carbon_intensity(mix) == 12.0


def test_power_breakdown_keeps_generating_fuels_rounded():
    mix = {"wind": 4200.4, "natural_gas": 1800.6, "battery": -100, "coal": 0}
    # Negative (storage charging) and zero fuels drop out; rest rounds to whole MW.
    assert power_breakdown(mix) == {"wind": 4200, "natural_gas": 1801}


def test_power_breakdown_empty_is_none():
    # No real generation -> field stays absent rather than an empty dict.
    assert power_breakdown({}) is None
    assert power_breakdown({"battery": -50}) is None


# ── Storage exclusion ──────────────────────────────────────────
# Discharge re-delivers energy whose emissions were attributed at generation.
# Leaving it in the denominator with a factor of 0 diluted intensity downward.


def test_discharging_storage_does_not_dilute_intensity():
    assert calculate_carbon_intensity({"coal": 500, "battery": 500}) == 820.0
    assert calculate_carbon_intensity({"coal": 500, "pumped_storage": 500}) == 820.0


def test_discharging_storage_does_not_inflate_renewable_percentage():
    # Half the MW on the wire is battery, but renewables are 100% of *generation*.
    assert calculate_renewable_percentage({"wind": 500, "battery": 500}) == 100.0


def test_storage_is_not_a_factor():
    for key in STORAGE_TYPES:
        assert key not in EMISSION_FACTORS
    with pytest.raises(FactorCorpusError, match="storage"):
        load_corpus().value("battery")


def test_marginal_ignores_storage():
    # Storage discharging is not the price-setting generator.
    assert calculate_marginal_intensity({"battery": 500, "wind": 500}) == 11.0
    assert calculate_marginal_intensity({"battery": 500, "natural_gas": 100}) == 490.0


# ── Corpus contract ────────────────────────────────────────────


def test_corpus_values_match_the_published_factors():
    corpus = load_corpus()
    assert corpus.unit == "gCO2eq/kWh"
    assert corpus.basis == "lifecycle"
    # Pinned so a silent edit to the JSON fails here rather than in production.
    assert corpus.value("coal") == 820
    assert corpus.value("natural_gas") == 490
    assert corpus.value("wind") == 11
    assert corpus.value("solar") == 48


def test_every_factor_states_a_basis():
    """No factor may reach the API with neither a citation nor a declared assumption."""
    for key, factor in load_corpus().factors.items():
        assert factor.citation or factor.assumption, f"{key} has no stated basis"
        if factor.is_assumed:
            assert factor.evidence_tier == "E", (
                f"{key} is assumed but claims tier {factor.evidence_tier}"
            )


def test_cited_factors_resolve_against_the_citation_corpus():
    citekeys = {e["id"] for e in json.loads(factor_corpus._CITATIONS_PATH.read_text())}
    for key, factor in load_corpus().factors.items():
        if factor.citation:
            assert factor.citation in citekeys, f"{key} cites unknown {factor.citation}"


def test_ipcc_backed_factors_sit_inside_the_published_range():
    """A value claiming an IPCC row must lie within that row's published min/max."""
    raw = json.loads(factor_corpus._CORPUS_PATH.read_text())
    checked = 0
    for record in raw["factors"]:
        rng = record.get("source_range")
        if not rng or record.get("value") is None:
            continue
        assert rng["min"] <= record["value"] <= rng["max"], (
            f"{record['key']}={record['value']} is outside its cited range {rng}"
        )
        checked += 1
    assert checked >= 8


def test_unknown_citekey_is_rejected():
    with pytest.raises(FactorCorpusError, match="not a citekey"):
        factor_corpus._parse_factor(
            {"key": "unobtainium", "value": 1, "evidence_tier": "A", "citation": "no-such-key"},
            citekeys={"ipcc-ar5-annex3"},
        )


def test_uncited_factor_without_an_assumption_is_rejected():
    with pytest.raises(FactorCorpusError, match="no citation"):
        factor_corpus._parse_factor(
            {"key": "guesswork", "value": 500, "evidence_tier": "E", "citation": None},
            citekeys=set(),
        )


def test_assumption_may_not_claim_a_high_evidence_tier():
    with pytest.raises(FactorCorpusError, match="claims evidence tier"):
        factor_corpus._parse_factor(
            {
                "key": "guesswork",
                "value": 500,
                "evidence_tier": "A",
                "citation": None,
                "assumption": "made up",
            },
            citekeys=set(),
        )


def test_storage_must_not_carry_a_value():
    with pytest.raises(FactorCorpusError, match="null value"):
        factor_corpus._parse_factor(
            {
                "key": "flywheel",
                "value": 0,
                "storage": True,
                "evidence_tier": "E",
                "citation": None,
                "assumption": "storage",
            },
            citekeys=set(),
        )


# ── The false-zero guard ───────────────────────────────────────
# A zero-generation mix averages to 0.0 gCO2/kWh, the best score a carbon-aware
# router can see, so a hollow feed would win every routing decision rather than
# merely going dark. Measured in the published archive: three NL regions sat at
# 0.0 for 23 hours. See docs/VALIDATION.md.


@pytest.mark.parametrize(
    "mix,label",
    [
        ({}, "empty"),
        ({"solar": 0.0, "wind": 0.0}, "present but all zero"),
        ({"solar": -5.0}, "negative only"),
        ({"battery": 500}, "discharging storage only"),
    ],
)
def test_non_generating_mix_refuses_to_publish_a_false_zero(mix, label):
    from datetime import UTC, datetime

    from carbonlens.carbon_sources.emission_factors import intensity_from_fuel_mix

    with pytest.raises(ValueError, match="no generation"):
        intensity_from_fuel_mix("NL", mix, "entsoe", datetime.now(UTC))


def test_a_real_mix_still_builds():
    from datetime import UTC, datetime

    from carbonlens.carbon_sources.emission_factors import intensity_from_fuel_mix

    reading = intensity_from_fuel_mix(
        "NL", {"battery": 500, "wind": 10}, "entsoe", datetime.now(UTC)
    )
    assert reading.carbon_intensity_gco2_kwh == 11.0
