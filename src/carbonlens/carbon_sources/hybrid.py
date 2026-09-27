"""Hybrid carbon source: cascading provider chain with automatic fallback.

_build_provider_chain is the source of truth for the priority order. The first
provider covering a zone wins, with Mock as the static last resort.
"""

import asyncio
import logging

from carbonlens.carbon_sources.aemo import AEMOCarbonSource
from carbonlens.carbon_sources.base import CarbonDataSource
from carbonlens.carbon_sources.canada import CanadaCarbonSource
from carbonlens.carbon_sources.eia import EIACarbonSource
from carbonlens.carbon_sources.entsoe import ENTSOECarbonSource
from carbonlens.carbon_sources.eskom import EskomCarbonSource
from carbonlens.carbon_sources.grid_india import GridIndiaCarbonSource
from carbonlens.carbon_sources.gridstatus import GridStatusCarbonSource
from carbonlens.carbon_sources.mock import MockCarbonSource
from carbonlens.carbon_sources.ons_brazil import ONSBrazilCarbonSource
from carbonlens.carbon_sources.open_meteo import OpenMeteoCarbonSource
from carbonlens.carbon_sources.taiwan import TaiwanCarbonSource
from carbonlens.carbon_sources.uk import UKCarbonSource
from carbonlens.models.carbon import CarbonIntensity

logger = logging.getLogger(__name__)


class HybridCarbonSource:
    def __init__(
        self,
        eia: EIACarbonSource | None = None,
        gridstatus: GridStatusCarbonSource | None = None,
        entsoe: ENTSOECarbonSource | None = None,
        electricity_maps: CarbonDataSource | None = None,
        mock: MockCarbonSource | None = None,
    ) -> None:
        # Free providers (no API key needed)
        self._uk = UKCarbonSource()
        self._aemo = AEMOCarbonSource()
        self._grid_india = GridIndiaCarbonSource()
        self._ons_brazil = ONSBrazilCarbonSource()
        self._eskom = EskomCarbonSource()
        self._canada = CanadaCarbonSource()
        self._taiwan = TaiwanCarbonSource()
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

    def can_handle(self, grid_zone: str) -> bool:
        # Always resolves: falls back to the static mock when nothing else covers it
        return True

    def _build_provider_chain(self) -> list[tuple[str, CarbonDataSource]]:
        """Build the ordered provider chain once at init time.

        Providers with ``None`` instances (missing API key) are skipped. Each
        provider's own ``can_handle`` decides zone coverage.
        """
        chain: list[tuple[str, CarbonDataSource]] = [
            ("UK", self._uk),
        ]
        if self._eia:
            chain.append(("EIA", self._eia))
        chain.extend(
            [
                ("AEMO", self._aemo),
                ("Canada", self._canada),
                ("Taiwan", self._taiwan),
                ("Grid India", self._grid_india),
                ("ONS Brazil", self._ons_brazil),
                ("Eskom", self._eskom),
            ]
        )
        if self._gridstatus:
            chain.append(("GridStatus", self._gridstatus))
        if self._entsoe:
            chain.append(("ENTSO-E", self._entsoe))
        chain.append(("Open-Meteo", self._open_meteo))
        if self._electricity_maps:
            chain.append(("Electricity Maps", self._electricity_maps))
        return chain

    async def get_carbon_intensity(self, grid_zone: str) -> CarbonIntensity:
        for name, provider in self._chain:
            if not provider.can_handle(grid_zone):
                continue
            try:
                result = await provider.get_carbon_intensity(grid_zone)
                logger.debug(
                    "%s hit for %s: %.1f gCO2/kWh",
                    name,
                    grid_zone,
                    result.carbon_intensity_gco2_kwh,
                )
                return result
            except Exception as e:
                logger.warning("%s failed for %s: %s", name, grid_zone, e)

        # Mock (static fallback, always succeeds). Reaching here means no real
        # provider covered the zone or every applicable one failed, so surface it
        # at INFO: a zone we normally measure going dark is worth seeing.
        result = await self._mock.get_carbon_intensity(grid_zone)
        logger.info("No live source for %s, using mock fallback", grid_zone)
        return result

    async def get_carbon_intensity_batch(self, grid_zones: list[str]) -> dict[str, CarbonIntensity]:
        """Fetch carbon data for multiple zones, fanning out to providers concurrently.

        All applicable providers are called in parallel via asyncio.gather.
        Results are merged in priority order so higher-priority providers win
        when multiple providers cover the same zone.
        """
        zone_set = set(grid_zones)

        # Build (priority, name, coroutine) for each provider that has matching zones
        tasks: list[tuple[int, str, asyncio.Task]] = []
        for priority, (name, provider) in enumerate(self._chain):
            batch_zones = [z for z in zone_set if provider.can_handle(z)]
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

        # Mock for anything remaining. These zones had no live/estimated source
        # this run, so log which ones at INFO. This is the signal that surfaces
        # in snapshot-builder logs when a feed goes dark.
        remaining = [z for z in grid_zones if z not in results]
        if remaining:
            logger.info(
                "No live source for %d/%d zone(s), using mock fallback: %s",
                len(remaining),
                len(grid_zones),
                ", ".join(sorted(remaining)),
            )
            mock_results = await self._mock.get_carbon_intensity_batch(remaining)
            results.update(mock_results)

        return results
