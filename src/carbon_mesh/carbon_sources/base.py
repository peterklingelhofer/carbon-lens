from typing import Protocol

from carbon_mesh.models.carbon import CarbonIntensity


class CarbonDataSource(Protocol):
    async def get_carbon_intensity(self, grid_zone: str) -> CarbonIntensity: ...

    async def get_carbon_intensity_batch(
        self, grid_zones: list[str]
    ) -> dict[str, CarbonIntensity]: ...
