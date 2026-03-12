from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from carbon_mesh.carbon_sources.mock import MockCarbonSource
from carbon_mesh.engine.cache import IntensityCache
from carbon_mesh.engine.router import RoutingEngine
from carbon_mesh.grid.mapper import GridMapper

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture
def grid_mapper() -> GridMapper:
    return GridMapper(DATA_DIR / "region_grid_map.yaml")


@pytest.fixture
def mock_source() -> MockCarbonSource:
    return MockCarbonSource()


@pytest.fixture
def cache() -> IntensityCache:
    return IntensityCache(ttl_seconds=60)


@pytest.fixture
def engine(grid_mapper: GridMapper, mock_source: MockCarbonSource, cache: IntensityCache) -> RoutingEngine:
    return RoutingEngine(carbon_source=mock_source, grid_mapper=grid_mapper, cache=cache)


@pytest.fixture
def client() -> TestClient:
    from carbon_mesh.main import app
    return TestClient(app)
