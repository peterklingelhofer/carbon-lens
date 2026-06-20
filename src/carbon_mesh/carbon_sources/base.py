from typing import Protocol

from carbon_mesh.models.carbon import CarbonIntensity


class CarbonDataSource(Protocol):
    async def get_carbon_intensity(self, grid_zone: str) -> CarbonIntensity: ...

    async def get_carbon_intensity_batch(
        self, grid_zones: list[str]
    ) -> dict[str, CarbonIntensity]: ...


class SingleZoneCarbonSource:
    """Base for providers that fetch one zone at a time and have no real batch API.

    The default batch loops over can_handle + get_carbon_intensity, omitting any
    zone whose fetch raises. Providers with real batching (EIA, UK, AEMO, Canada,
    Taiwan) override get_carbon_intensity_batch instead of subclassing this.
    """

    def can_handle(self, grid_zone: str) -> bool:
        raise NotImplementedError

    async def get_carbon_intensity(self, grid_zone: str) -> CarbonIntensity:
        raise NotImplementedError

    async def get_carbon_intensity_batch(self, grid_zones: list[str]) -> dict[str, CarbonIntensity]:
        results: dict[str, CarbonIntensity] = {}
        for zone in grid_zones:
            if not self.can_handle(zone):
                continue
            try:
                results[zone] = await self.get_carbon_intensity(zone)
            except Exception:
                pass
        return results
