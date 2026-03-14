"""Hybrid carbon source — cascading provider chain with automatic fallback.

Priority order:
1. UK Carbon Intensity API (GB zones, free, no key)
2. EIA API (US zones, free, real-time hourly)
3. AEMO (Australian zones, free, 5-min)
4. Grid India (Indian zones, free)
5. ONS Brazil (Brazilian zones, free)
6. Eskom (South Africa, heuristic)
7. GridStatus.io (US ISOs, 5-min — paid tier for real-time)
8. ENTSO-E (EU zones, requires free token)
9. Open-Meteo (weather-based, worldwide, free)
10. Electricity Maps (global, paid API key)
11. Mock (static fallback for anything remaining)
"""

import asyncio
import logging

from carbon_mesh.carbon_sources.aemo import AEMOCarbonSource, AEMO_ZONES
from carbon_mesh.carbon_sources.eia import EIACarbonSource, _GRID_ZONE_TO_EIA
from carbon_mesh.carbon_sources.entsoe import ENTSOECarbonSource, ENTSOE_ZONES
from carbon_mesh.carbon_sources.eskom import EskomCarbonSource, ESKOM_ZONES
from carbon_mesh.carbon_sources.grid_india import GridIndiaCarbonSource, INDIA_ZONES
from carbon_mesh.carbon_sources.gridstatus import GridStatusCarbonSource, _GRID_ZONE_TO_ISO
from carbon_mesh.carbon_sources.mock import MockCarbonSource
from carbon_mesh.carbon_sources.ons_brazil import ONSBrazilCarbonSource, BRAZIL_ZONES
from carbon_mesh.carbon_sources.open_meteo import OpenMeteoCarbonSource, ZONE_COORDINATES
from carbon_mesh.carbon_sources.uk import UKCarbonSource, UK_ZONES
from carbon_mesh.models.carbon import CarbonIntensity

logger = logging.getLogger(__name__)


class HybridCarbonSource:
    def __init__(
        self,
        eia: EIACarbonSource | None = None,
        gridstatus: GridStatusCarbonSource | None = None,
        entsoe: ENTSOECarbonSource | None = None,
        electricity_maps: object | None = None,
        mock: MockCarbonSource | None = None,
    ) -> None:
        # Free providers (no API key needed)
        self._uk = UKCarbonSource()
        self._aemo = AEMOCarbonSource()
        self._grid_india = GridIndiaCarbonSource()
        self._ons_brazil = ONSBrazilCarbonSource()
        self._eskom = EskomCarbonSource()
        self._open_meteo = OpenMeteoCarbonSource()

        # Key-based providers
        self._eia = eia
        self._gridstatus = gridstatus
        self._entsoe = entsoe
        self._electricity_maps = electricity_maps

        # Ultimate fallback
        self._mock = mock or MockCarbonSource()

        # Precompute the provider chain once (immutable after init)
        self._chain = self._build_provider_chain()

    def _build_provider_chain(self) -> list[tuple[str, object, set[str]]]:
        """Build the ordered provider chain once at init time.

        Providers with ``None`` instances (missing API key) are skipped.
        Electricity Maps accepts any zone so uses an empty sentinel set handled
        specially by callers.
        """
        chain: list[tuple[str, object, set[str]]] = [
            ("UK", self._uk, UK_ZONES),
        ]
        if self._eia:
            chain.append(("EIA", self._eia, set(_GRID_ZONE_TO_EIA.keys())))
        chain.extend([
            ("AEMO", self._aemo, AEMO_ZONES),
            ("Grid India", self._grid_india, INDIA_ZONES),
            ("ONS Brazil", self._ons_brazil, BRAZIL_ZONES),
            ("Eskom", self._eskom, ESKOM_ZONES),
        ])
        if self._gridstatus:
            chain.append(("GridStatus", self._gridstatus, set(_GRID_ZONE_TO_ISO.keys())))
        if self._entsoe:
            chain.append(("ENTSO-E", self._entsoe, ENTSOE_ZONES))
        chain.append(("Open-Meteo", self._open_meteo, set(ZONE_COORDINATES.keys())))
        if self._electricity_maps:
            # Electricity Maps is a global fallback — accepts any zone
            chain.append(("Electricity Maps", self._electricity_maps, set()))
        return chain

    async def get_carbon_intensity(self, grid_zone: str) -> CarbonIntensity:
        for name, provider, supported_zones in self._chain:
            # Empty supported_zones means "accepts any zone" (e.g. Electricity Maps)
            if supported_zones and grid_zone not in supported_zones:
                continue
            try:
                result = await provider.get_carbon_intensity(grid_zone)
                logger.debug("%s hit for %s: %.1f gCO2/kWh", name, grid_zone, result.carbon_intensity_gco2_kwh)
                return result
            except Exception as e:
                logger.warning("%s failed for %s: %s", name, grid_zone, e)

        # Mock (static fallback — always succeeds)
        result = await self._mock.get_carbon_intensity(grid_zone)
        logger.debug("Mock fallback for %s: %.1f gCO2/kWh", grid_zone, result.carbon_intensity_gco2_kwh)
        return result

    async def get_carbon_intensity_batch(
        self, grid_zones: list[str]
    ) -> dict[str, CarbonIntensity]:
        """Fetch carbon data for multiple zones, fanning out to providers concurrently.

        All applicable providers are called in parallel via asyncio.gather.
        Results are merged in priority order so higher-priority providers win
        when multiple providers cover the same zone.
        """
        zone_set = set(grid_zones)

        # Build (priority, name, coroutine) for each provider that has matching zones
        tasks: list[tuple[int, str, asyncio.Task]] = []
        for priority, (name, provider, supported_zones) in enumerate(self._chain):
            batch_zones = list(zone_set) if not supported_zones else [z for z in zone_set if z in supported_zones]
            if not batch_zones:
                continue
            coro = provider.get_carbon_intensity_batch(batch_zones)
            tasks.append((priority, name, asyncio.ensure_future(coro)))

        # Await all concurrently
        if tasks:
            await asyncio.gather(*(t for _, _, t in tasks), return_exceptions=True)

        # Merge in reverse priority order (lowest priority first) so highest-priority wins
        results: dict[str, CarbonIntensity] = {}
        for priority, name, task in sorted(tasks, key=lambda t: -t[0]):
            if task.cancelled():
                continue
            exc = task.exception()
            if exc is not None:
                logger.warning("%s batch failed: %s", name, exc)
                continue
            batch_results = task.result()
            if batch_results:
                logger.debug("%s batch: got %d zones", name, len(batch_results))
                results.update(batch_results)

        # Mock for anything remaining
        remaining = [z for z in grid_zones if z not in results]
        if remaining:
            mock_results = await self._mock.get_carbon_intensity_batch(remaining)
            results.update(mock_results)

        return results
