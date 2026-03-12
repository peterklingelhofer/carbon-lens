from carbon_mesh.carbon_sources.emission_factors import (
    calculate_carbon_intensity,
    calculate_renewable_percentage,
)


def test_pure_wind():
    mix = {"wind": 1000}
    assert calculate_carbon_intensity(mix) == 11.0
    assert calculate_renewable_percentage(mix) == 100.0


def test_pure_coal():
    mix = {"coal": 1000}
    assert calculate_carbon_intensity(mix) == 900.0
    assert calculate_renewable_percentage(mix) == 0.0


def test_mixed_grid():
    mix = {"wind": 500, "natural_gas": 500}
    intensity = calculate_carbon_intensity(mix)
    # (500*11 + 500*430) / 1000 = 220.5
    assert abs(intensity - 220.5) < 0.1
    assert calculate_renewable_percentage(mix) == 50.0


def test_empty_mix():
    assert calculate_carbon_intensity({}) == 0.0
    assert calculate_renewable_percentage({}) == 0.0


def test_negative_values_ignored():
    # Battery discharging can show as negative
    mix = {"solar": 500, "battery": -100, "natural_gas": 200}
    total_positive = 500 + 200  # battery excluded
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
