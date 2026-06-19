"""Tests for the optional measured-marginal (WattTime) source."""

from carbon_mesh.carbon_sources.marginal import (
    WattTimeMarginalSource,
    marginal_source_from_settings,
    moer_to_gco2_kwh,
    parse_zone_map,
)


def test_moer_conversion():
    # 1000 lbs CO2/MWh -> 453.6 g CO2/kWh (1 lb = 453.59237 g; 1 MWh = 1000 kWh).
    assert moer_to_gco2_kwh(1000) == 453.6
    assert moer_to_gco2_kwh(0) == 0.0


def test_parse_zone_map():
    m = parse_zone_map("US-CAL-CISO:CAISO_NORTH, US-MIDA-PJM:PJM_DC ,bad-entry")
    assert m == {"US-CAL-CISO": "CAISO_NORTH", "US-MIDA-PJM": "PJM_DC"}
    assert parse_zone_map("") == {}


async def test_watttime_source_converts_and_skips_unmapped(monkeypatch):
    src = WattTimeMarginalSource("tok", {"US-CAL-CISO": "CAISO_NORTH"})

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"data": [{"point_time": "2026-06-18T00:00:00Z", "value": 800.0}]}

    async def fake_get(url, params=None, headers=None):
        return FakeResp()

    monkeypatch.setattr(src._client, "get", fake_get)
    assert await src.marginal_intensity("US-CAL-CISO") == moer_to_gco2_kwh(800)
    # An unmapped zone returns None (so it stays on the heuristic).
    assert await src.marginal_intensity("XX-UNMAPPED") is None


def test_parse_moer_forecast():
    from datetime import datetime, timezone

    from carbon_mesh.carbon_sources.marginal import moer_to_gco2_kwh, parse_moer_forecast

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    data = [
        {"point_time": "2026-06-18T12:00:00Z", "value": 800},  # offset 0
        {"point_time": "2026-06-18T14:00:00Z", "value": 400},  # offset 2
        {"point_time": "2026-06-17T12:00:00Z", "value": 999},  # past -> dropped
    ]
    curve = parse_moer_forecast(data, now, hours=24)
    assert curve == {0: moer_to_gco2_kwh(800), 2: moer_to_gco2_kwh(400)}


def test_parse_em_forecast():
    from datetime import datetime, timezone

    from carbon_mesh.carbon_sources.marginal import parse_em_forecast

    now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
    data = [
        {"datetime": "2026-06-18T12:00:00Z", "marginalCarbonIntensity": 300},  # offset 0
        {"datetime": "2026-06-18T15:00:00Z", "marginalCarbonIntensity": 120},  # offset 3
        {"datetime": "2026-06-17T12:00:00Z", "marginalCarbonIntensity": 999},  # past -> dropped
    ]
    assert parse_em_forecast(data, now, hours=24) == {0: 300.0, 3: 120.0}


async def test_electricity_maps_source_reads_marginal(monkeypatch):
    from carbon_mesh.carbon_sources.marginal import ElectricityMapsMarginalSource

    src = ElectricityMapsMarginalSource("tok", {"FR": "FR"})

    class FakeResp:
        def raise_for_status(self):
            return None

        def json(self):
            return {"marginalCarbonIntensity": 88.0}  # already g/kWh

    async def fake_get(url, params=None, headers=None):
        assert headers == {"auth-token": "tok"}
        return FakeResp()

    monkeypatch.setattr(src._client, "get", fake_get)
    assert await src.marginal_intensity("FR") == 88.0
    assert await src.marginal_intensity("XX") is None


def test_factory_prefers_watttime_then_electricity_maps():
    from carbon_mesh.carbon_sources.marginal import (
        ElectricityMapsMarginalSource,
        WattTimeMarginalSource,
        marginal_source_from_settings,
    )

    class Both:
        watttime_token = "wt"
        watttime_zone_map = "US-CAL-CISO:CAISO_NORTH"
        electricity_maps_api_key = "em"
        electricity_maps_zone_map = "FR:FR"

    class EMOnly:
        watttime_token = ""
        watttime_zone_map = ""
        electricity_maps_api_key = "em"
        electricity_maps_zone_map = "FR:FR"

    assert isinstance(marginal_source_from_settings(Both()), WattTimeMarginalSource)
    assert isinstance(marginal_source_from_settings(EMOnly()), ElectricityMapsMarginalSource)


def test_factory_is_off_without_token_or_map():
    class NoToken:
        watttime_token = ""
        watttime_zone_map = "US-CAL-CISO:CAISO_NORTH"

    class NoMap:
        watttime_token = "tok"
        watttime_zone_map = ""

    class Configured:
        watttime_token = "tok"
        watttime_zone_map = "US-CAL-CISO:CAISO_NORTH"

    assert marginal_source_from_settings(NoToken()) is None
    assert marginal_source_from_settings(NoMap()) is None
    assert marginal_source_from_settings(Configured()) is not None


def test_marginal_unmapped_flags_only_the_silent_trap():
    from carbon_mesh.carbon_sources.marginal import marginal_unmapped

    class KeyNoMap:  # the trap: token set, no zone map
        watttime_token = "tok"
        watttime_zone_map = ""

    class EMKeyNoMap:
        electricity_maps_api_key = "k"
        electricity_maps_zone_map = ""

    class Configured:  # properly mapped -> not a trap
        watttime_token = "tok"
        watttime_zone_map = "US-CAL-CISO:CAISO_NORTH"

    class Nothing:  # no credential at all -> deliberate heuristic, not a trap
        pass

    assert marginal_unmapped(KeyNoMap()) is True
    assert marginal_unmapped(EMKeyNoMap()) is True
    assert marginal_unmapped(Configured()) is False
    assert marginal_unmapped(Nothing()) is False
