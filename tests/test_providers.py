"""Tests for all carbon data source providers.

Each provider is tested for:
1. Zone coverage (can_handle returns correct values)
2. Data structure (returns valid CarbonIntensity)
3. Batch operation
4. Heuristic/fallback behavior where applicable
"""

import pytest

from carbon_mesh.carbon_sources.aemo import AEMOCarbonSource, AEMO_ZONES
from carbon_mesh.carbon_sources.eia import _GRID_ZONE_TO_EIA
from carbon_mesh.carbon_sources.entsoe import ENTSOECarbonSource, ENTSOE_ZONES
from carbon_mesh.carbon_sources.eskom import EskomCarbonSource, ESKOM_ZONES
from carbon_mesh.carbon_sources.grid_india import GridIndiaCarbonSource, INDIA_ZONES
from carbon_mesh.carbon_sources.gridstatus import _GRID_ZONE_TO_ISO
from carbon_mesh.carbon_sources.mock import MockCarbonSource
from carbon_mesh.carbon_sources.ons_brazil import ONSBrazilCarbonSource, BRAZIL_ZONES
from carbon_mesh.carbon_sources.open_meteo import OpenMeteoCarbonSource, ZONE_COORDINATES
from carbon_mesh.carbon_sources.uk import UKCarbonSource


# ---------------------------------------------------------------------------
# Zone coverage tests
# ---------------------------------------------------------------------------


class TestZoneCoverage:
    def test_uk_zones(self):
        source = UKCarbonSource()
        assert source.can_handle("GB")
        assert source.can_handle("GB-1")
        assert source.can_handle("GB-17")
        assert not source.can_handle("DE")

    def test_aemo_zones(self):
        source = AEMOCarbonSource()
        assert source.can_handle("AU-NSW")
        assert source.can_handle("AU-TAS")
        assert not source.can_handle("GB")
        assert AEMO_ZONES == {"AU-NSW", "AU-QLD", "AU-VIC", "AU-SA", "AU-TAS"}

    def test_india_zones(self):
        source = GridIndiaCarbonSource()
        assert source.can_handle("IN-NO")
        assert source.can_handle("IN-SO")
        assert not source.can_handle("US-MIDA-PJM")
        assert INDIA_ZONES == {"IN-NO", "IN-SO", "IN-EA", "IN-WE", "IN-NE"}

    def test_brazil_zones(self):
        source = ONSBrazilCarbonSource()
        assert source.can_handle("BR-S")
        assert source.can_handle("BR-NE")
        assert not source.can_handle("IN-NO")
        assert BRAZIL_ZONES == {"BR-S", "BR-SE", "BR-NE", "BR-N", "BR-CS"}

    def test_eskom_zones(self):
        source = EskomCarbonSource()
        assert source.can_handle("ZA")
        assert not source.can_handle("GB")
        assert ESKOM_ZONES == {"ZA"}

    def test_entsoe_zones(self):
        assert "DE" in ENTSOE_ZONES
        assert "FR" in ENTSOE_ZONES
        assert "SE-SE3" in ENTSOE_ZONES
        assert "NO-NO1" in ENTSOE_ZONES
        assert len(ENTSOE_ZONES) >= 36

    def test_eia_zones(self):
        assert "US-MIDA-PJM" in _GRID_ZONE_TO_EIA
        assert "US-CAL-CISO" in _GRID_ZONE_TO_EIA
        assert len(_GRID_ZONE_TO_EIA) >= 7

    def test_gridstatus_zones(self):
        assert "US-MIDA-PJM" in _GRID_ZONE_TO_ISO
        assert "US-CAL-CISO" in _GRID_ZONE_TO_ISO

    def test_open_meteo_zones(self):
        source = OpenMeteoCarbonSource()
        assert source.can_handle("JP-TK")
        assert source.can_handle("KR")
        assert source.can_handle("SG")
        assert source.can_handle("IS")
        assert len(ZONE_COORDINATES) >= 40


# ---------------------------------------------------------------------------
# Eskom heuristic tests (no API needed)
# ---------------------------------------------------------------------------


class TestEskomHeuristic:
    @pytest.mark.asyncio
    async def test_returns_high_intensity(self):
        source = EskomCarbonSource()
        result = await source.get_carbon_intensity("ZA")
        # South Africa is coal-heavy, should be > 700
        assert result.carbon_intensity_gco2_kwh >= 700
        assert result.renewable_percentage <= 20
        assert result.source == "eskom_heuristic"
        assert result.grid_zone == "ZA"

    @pytest.mark.asyncio
    async def test_batch(self):
        source = EskomCarbonSource()
        results = await source.get_carbon_intensity_batch(["ZA", "GB"])
        assert "ZA" in results
        assert "GB" not in results  # Eskom doesn't handle GB


# ---------------------------------------------------------------------------
# Grid India heuristic tests (fallback when API is unavailable)
# ---------------------------------------------------------------------------


class TestGridIndiaHeuristic:
    @pytest.mark.asyncio
    async def test_all_regions(self):
        source = GridIndiaCarbonSource()
        for zone in INDIA_ZONES:
            result = await source.get_carbon_intensity(zone)
            assert result.carbon_intensity_gco2_kwh > 0
            assert 0 <= result.renewable_percentage <= 100
            assert result.grid_zone == zone

    @pytest.mark.asyncio
    async def test_invalid_zone(self):
        source = GridIndiaCarbonSource()
        with pytest.raises(ValueError, match="Unknown India zone"):
            await source.get_carbon_intensity("US-MIDA-PJM")


# ---------------------------------------------------------------------------
# ONS Brazil heuristic tests
# ---------------------------------------------------------------------------


class TestONSBrazilHeuristic:
    @pytest.mark.asyncio
    async def test_all_regions(self):
        source = ONSBrazilCarbonSource()
        for zone in BRAZIL_ZONES:
            result = await source.get_carbon_intensity(zone)
            assert result.carbon_intensity_gco2_kwh > 0
            # Brazil is mostly hydro — renewable should be high
            assert result.renewable_percentage >= 50
            assert result.grid_zone == zone

    @pytest.mark.asyncio
    async def test_batch(self):
        source = ONSBrazilCarbonSource()
        results = await source.get_carbon_intensity_batch(list(BRAZIL_ZONES))
        assert len(results) == 5


# ---------------------------------------------------------------------------
# Mock source tests (all zones)
# ---------------------------------------------------------------------------


class TestMockSource:
    @pytest.mark.asyncio
    async def test_known_zone(self):
        source = MockCarbonSource()
        result = await source.get_carbon_intensity("CA-QC")
        assert result.carbon_intensity_gco2_kwh == 10
        assert result.renewable_percentage == 99

    @pytest.mark.asyncio
    async def test_unknown_zone_defaults(self):
        source = MockCarbonSource()
        result = await source.get_carbon_intensity("UNKNOWN-ZONE")
        assert result.carbon_intensity_gco2_kwh == 250
        assert result.renewable_percentage == 30

    @pytest.mark.asyncio
    async def test_new_zones_covered(self):
        """Verify all newly added zones have mock data."""
        source = MockCarbonSource()
        new_zones = [
            "AU-NSW",
            "AU-TAS",
            "IN-NO",
            "IN-SO",
            "BR-SE",
            "BR-NE",
            "ZA",
            "KR",
            "HK",
            "NO-NO1",
            "PL",
            "ES",
            "IS",
            "UY",
            "CR",
        ]
        for zone in new_zones:
            result = await source.get_carbon_intensity(zone)
            # Should NOT return the default (250, 30) — should have specific data
            assert (result.carbon_intensity_gco2_kwh, result.renewable_percentage) != (250, 30), (
                f"Zone {zone} is using default mock data"
            )

    @pytest.mark.asyncio
    async def test_batch(self):
        source = MockCarbonSource()
        zones = ["CA-QC", "ZA", "AU-TAS", "UNKNOWN"]
        results = await source.get_carbon_intensity_batch(zones)
        assert len(results) == 4
        assert results["CA-QC"].carbon_intensity_gco2_kwh == 10
        assert results["ZA"].carbon_intensity_gco2_kwh == 780


# ---------------------------------------------------------------------------
# UK source tests (structure only — actual API tested via integration)
# ---------------------------------------------------------------------------


class TestUKSource:
    def test_zone_mapping(self):
        source = UKCarbonSource()
        assert source.can_handle("GB")
        for i in range(1, 18):
            assert source.can_handle(f"GB-{i}")
        assert not source.can_handle("GB-0")
        assert not source.can_handle("GB-18")

    @pytest.mark.asyncio
    async def test_invalid_zone(self):
        source = UKCarbonSource()
        with pytest.raises(ValueError, match="Unknown UK zone"):
            await source.get_carbon_intensity("GB-99")


# ---------------------------------------------------------------------------
# ENTSO-E zone map tests
# ---------------------------------------------------------------------------


class TestENTSOE:
    def test_zone_map_complete(self):
        """ENTSO-E should have EIC codes for all major EU countries."""
        from carbon_mesh.carbon_sources.entsoe import ENTSOE_ZONE_MAP

        required = ["DE", "FR", "ES", "NL", "BE", "PL", "FI", "IE", "NO-NO1", "SE-SE3"]
        for zone in required:
            assert zone in ENTSOE_ZONE_MAP, f"Missing ENTSO-E zone: {zone}"

    def test_can_handle(self):
        source = ENTSOECarbonSource(security_token="test")
        assert source.can_handle("DE")
        assert source.can_handle("FR")
        assert not source.can_handle("US-MIDA-PJM")
        assert not source.can_handle("AU-NSW")


# ---------------------------------------------------------------------------
# Open-Meteo tests
# ---------------------------------------------------------------------------


class TestOpenMeteo:
    def test_coordinate_coverage(self):
        """Open-Meteo should have coordinates for major zones not covered by other providers."""
        required = ["JP-TK", "KR", "SG", "TW", "HK", "AE", "IL", "IS", "NZ-NZN"]
        for zone in required:
            assert zone in ZONE_COORDINATES, f"Missing Open-Meteo coordinates: {zone}"

    def test_can_handle(self):
        source = OpenMeteoCarbonSource()
        assert source.can_handle("JP-TK")
        assert source.can_handle("IS")
        # Zones covered by other providers may also have coordinates (for fallback)
        assert source.can_handle("GB")


# ---------------------------------------------------------------------------
# Hybrid source tests (using mock internals)
# ---------------------------------------------------------------------------


class TestHybridSource:
    @pytest.mark.asyncio
    async def test_routes_to_correct_provider(self):
        """Hybrid should use specialized providers when available."""
        from carbon_mesh.carbon_sources.hybrid import HybridCarbonSource

        hybrid = HybridCarbonSource()

        # Eskom for ZA (heuristic, always works)
        za_result = await hybrid.get_carbon_intensity("ZA")
        assert za_result.source == "eskom_heuristic"

        # Grid India for IN zones (heuristic fallback)
        in_result = await hybrid.get_carbon_intensity("IN-SO")
        assert "grid_india" in in_result.source

        # ONS Brazil for BR zones (heuristic fallback)
        br_result = await hybrid.get_carbon_intensity("BR-S")
        assert "ons_brazil" in br_result.source

    @pytest.mark.asyncio
    async def test_falls_back_to_mock(self):
        """Unknown zones should fall back to mock."""
        from carbon_mesh.carbon_sources.hybrid import HybridCarbonSource

        hybrid = HybridCarbonSource()
        result = await hybrid.get_carbon_intensity("TOTALLY-UNKNOWN")
        assert result.source == "mock"

    @pytest.mark.asyncio
    async def test_batch_covers_all_zones(self):
        """Batch should return results for all requested zones."""
        from carbon_mesh.carbon_sources.hybrid import HybridCarbonSource

        hybrid = HybridCarbonSource()
        zones = ["ZA", "IN-NO", "BR-S", "UNKNOWN"]
        results = await hybrid.get_carbon_intensity_batch(zones)
        assert len(results) == 4
        assert all(z in results for z in zones)

    @pytest.mark.asyncio
    async def test_mock_fallback_is_logged(self, caplog):
        """A zone with no live source should surface at INFO, not silently."""
        import logging

        from carbon_mesh.carbon_sources.hybrid import HybridCarbonSource

        hybrid = HybridCarbonSource()
        with caplog.at_level(logging.INFO, logger="carbon_mesh.carbon_sources.hybrid"):
            await hybrid.get_carbon_intensity("TOTALLY-UNKNOWN")
        assert any(
            "mock fallback" in r.message and "TOTALLY-UNKNOWN" in r.message for r in caplog.records
        )

    @pytest.mark.asyncio
    async def test_batch_mock_fallback_names_the_zones(self, caplog):
        """The batch fall-through log should name the dark zones for debugging."""
        import logging

        from carbon_mesh.carbon_sources.hybrid import HybridCarbonSource

        hybrid = HybridCarbonSource()
        with caplog.at_level(logging.INFO, logger="carbon_mesh.carbon_sources.hybrid"):
            await hybrid.get_carbon_intensity_batch(["ZA", "UNKNOWN-A", "UNKNOWN-B"])
        msgs = [r.message for r in caplog.records if "mock fallback" in r.message]
        assert msgs and "UNKNOWN-A" in msgs[-1] and "UNKNOWN-B" in msgs[-1]
