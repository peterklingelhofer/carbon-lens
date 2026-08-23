"""Regression tests for the UK provider.

Both defects here were found by the audit in docs/VERIFICATION.md and both were
silent: one produced a wrong number, the other produced no number at all while the
README advertised 18 live zones.
"""

import pytest

from carbonlens.carbon_sources.uk import (
    _region_intensity,
    _renewable_or_zero,
    renewable_pct_from_mix,
)

# The shape NESO's /regional endpoint actually returns: forecast and index only.
REGIONAL = {
    "regionid": 1,
    "shortname": "North Scotland",
    "intensity": {"forecast": 0, "index": "very low"},
    "generationmix": [
        {"fuel": "biomass", "perc": 0},
        {"fuel": "coal", "perc": 0},
        {"fuel": "imports", "perc": 0},
        {"fuel": "gas", "perc": 0},
        {"fuel": "nuclear", "perc": 0},
        {"fuel": "other", "perc": 0},
        {"fuel": "hydro", "perc": 0},
        {"fuel": "solar", "perc": 0.2},
        {"fuel": "wind", "perc": 99.8},
    ],
}


class TestRegionalIntensity:
    def test_regional_payload_without_actual_still_resolves(self):
        """The bug: ["actual"] raised KeyError on every one of the 17 regional zones."""
        assert _region_intensity(REGIONAL) == 0.0

    def test_actual_wins_when_present(self):
        region = {"intensity": {"actual": 120, "forecast": 130}}
        assert _region_intensity(region) == 120.0

    def test_forecast_used_when_actual_is_null(self):
        region = {"intensity": {"actual": None, "forecast": 130}}
        assert _region_intensity(region) == 130.0

    def test_a_zero_forecast_is_not_treated_as_missing(self):
        """0 is a legitimate NESO value for a wind-dominated region on their direct
        basis, so it must not be coerced away by an `or` chain."""
        assert _region_intensity({"intensity": {"actual": None, "forecast": 0}}) == 0.0

    def test_missing_intensity_raises_rather_than_inventing(self):
        with pytest.raises(ValueError, match="no intensity"):
            _region_intensity({"regionid": 4, "intensity": {"index": "low"}})


class TestRenewableFromMix:
    def test_reads_the_published_mix(self):
        assert (
            renewable_pct_from_mix([{"fuel": "wind", "perc": 40}, {"fuel": "gas", "perc": 60}])
            == 40.0
        )

    def test_biomass_is_not_renewable(self):
        """Matches the emission-factor corpus: biomass is combustion, and the
        biogenic-CO2 accounting that would make it renewable is contested."""
        assert (
            renewable_pct_from_mix([{"fuel": "biomass", "perc": 50}, {"fuel": "gas", "perc": 50}])
            == 0.0
        )

    def test_imports_are_not_renewable(self):
        assert (
            renewable_pct_from_mix([{"fuel": "imports", "perc": 30}, {"fuel": "wind", "perc": 70}])
            == 70.0
        )

    def test_wind_solar_hydro_all_count(self):
        mix = [
            {"fuel": "wind", "perc": 30},
            {"fuel": "solar", "perc": 10},
            {"fuel": "hydro", "perc": 10},
            {"fuel": "gas", "perc": 50},
        ]
        assert renewable_pct_from_mix(mix) == 50.0

    def test_absent_or_empty_mix_returns_none_not_a_guess(self):
        assert renewable_pct_from_mix([]) is None
        assert renewable_pct_from_mix([{"fuel": "wind", "perc": 0}]) is None

    def test_region_helper_degrades_to_zero(self):
        assert _renewable_or_zero(REGIONAL) == 100.0
        assert _renewable_or_zero({"regionid": 2}) == 0.0


def test_the_old_estimator_is_the_one_that_was_wrong():
    """Pins the measured failure so the deprecated function is never quietly reused.

    Measured over 97 NESO settlement periods: mean error +46.9 percentage points,
    never negative. Here, a half-hour whose true renewable share was 7.8%.
    """
    from carbonlens.carbon_sources.uk import _estimate_renewable_pct

    assert _estimate_renewable_pct(172.0) == 61.8  # truth that period: 7.8%
