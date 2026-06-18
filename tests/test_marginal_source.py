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
