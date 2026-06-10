from typing import AsyncGenerator

from carbon_mesh.accounting.tracker import CarbonTracker, DBCarbonTracker
from carbon_mesh.carbon_sources.base import CarbonDataSource
from carbon_mesh.carbon_sources.eia import EIACarbonSource
from carbon_mesh.carbon_sources.electricity_maps import ElectricityMapsCarbonSource
from carbon_mesh.carbon_sources.entsoe import ENTSOECarbonSource
from carbon_mesh.carbon_sources.gridstatus import GridStatusCarbonSource
from carbon_mesh.carbon_sources.hybrid import HybridCarbonSource
from carbon_mesh.carbon_sources.mock import MockCarbonSource
from carbon_mesh.config import settings
from carbon_mesh.engine.cache import IntensityCache
from carbon_mesh.engine.router import RoutingEngine
from carbon_mesh.grid.mapper import GridMapper

# Singletons — initialized once at import time
_grid_mapper = GridMapper(settings.region_map_path)
_cache = IntensityCache(ttl_seconds=settings.cache_ttl_seconds)
_tracker = CarbonTracker()
_db_tracker = DBCarbonTracker()


class _CachedCarbonSource:
    """Wraps a carbon source with the shared stale-while-revalidate cache, so
    repeat reads (scheduler, bestNow, carbon API) don't each re-fetch every zone
    from upstream. Without this the scheduler re-hit ~40 live zones per request."""

    def __init__(self, source: CarbonDataSource, cache: IntensityCache) -> None:
        self._source = source
        self._cache = cache

    async def get_carbon_intensity(self, grid_zone: str):
        return await self._cache.get_or_fetch(grid_zone, self._source.get_carbon_intensity)

    async def get_carbon_intensity_batch(self, grid_zones: list[str]):
        return await self._cache.get_or_fetch_batch(
            grid_zones, self._source.get_carbon_intensity_batch
        )


def _build_carbon_source() -> CarbonDataSource:
    if settings.carbon_source == "electricity_maps":
        return ElectricityMapsCarbonSource(api_key=settings.electricity_maps_api_key)

    if settings.carbon_source == "eia":
        return EIACarbonSource(api_key=settings.eia_api_key)

    if settings.carbon_source == "gridstatus":
        return GridStatusCarbonSource(api_key=settings.grid_status_api_key)

    if settings.carbon_source == "hybrid":
        gridstatus = (
            GridStatusCarbonSource(api_key=settings.grid_status_api_key)
            if settings.grid_status_api_key
            else None
        )
        eia = EIACarbonSource(api_key=settings.eia_api_key) if settings.eia_api_key else None
        entsoe = (
            ENTSOECarbonSource(security_token=settings.entsoe_token)
            if settings.entsoe_token
            else None
        )
        electricity_maps = (
            ElectricityMapsCarbonSource(api_key=settings.electricity_maps_api_key)
            if settings.electricity_maps_api_key
            else None
        )
        return HybridCarbonSource(
            eia=eia,
            gridstatus=gridstatus,
            entsoe=entsoe,
            electricity_maps=electricity_maps,
        )

    return MockCarbonSource()


_carbon_source = _build_carbon_source()
_cached_source = _CachedCarbonSource(_carbon_source, _cache)
_engine = RoutingEngine(
    carbon_source=_carbon_source,
    grid_mapper=_grid_mapper,
    cache=_cache,
)


def get_engine() -> RoutingEngine:
    return _engine


def get_grid_mapper() -> GridMapper:
    return _grid_mapper


def get_carbon_source() -> CarbonDataSource:
    return _cached_source


def get_tracker() -> CarbonTracker:
    return _tracker


def get_db_tracker() -> DBCarbonTracker:
    return _db_tracker


async def get_session() -> AsyncGenerator:
    if not settings.use_database:
        yield None
        return
    from carbon_mesh.db.engine import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        yield session
