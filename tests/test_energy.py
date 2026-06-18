"""Tests for the RAPL energy meter (pure conversion + wrap-around)."""

from carbon_mesh.cli.energy import energy_kwh_between


def test_energy_kwh_between_basic():
    # 3.6e9 microjoules = 3600 J = 0.001 kWh.
    assert energy_kwh_between(0, 3_600_000_000, 0) == 0.001


def test_energy_kwh_between_handles_wrap():
    # Counter wrapped: after < before, add max_range once.
    kwh = energy_kwh_between(before_uj=9, after_uj=1, max_range_uj=3_600_000_009)
    # delta = (1 - 9) + 3_600_000_009 = 3_600_000_001 uj ≈ 3600 J = 0.001 kWh.
    assert round(kwh, 6) == 0.001


def test_energy_kwh_between_no_negative():
    # No wrap range available and counter went backwards -> clamp to 0.
    assert energy_kwh_between(100, 50, 0) == 0.0
