from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from carbon_mesh.carbon_sources.mock import MockCarbonSource
from carbon_mesh.config import settings
from carbon_mesh.engine.cache import IntensityCache
from carbon_mesh.engine.router import RoutingEngine
from carbon_mesh.grid.mapper import GridMapper

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@pytest.fixture(autouse=True)
def _demo_mode_no_auth():
    """Run the suite in open demo mode — auth defaults to fail-closed in production,
    and the rate limiter is disabled so back-to-back test requests don't trip it."""
    from carbon_mesh.main import limiter

    original_auth = settings.api_key_required
    original_enabled = limiter.enabled
    settings.api_key_required = False
    limiter.enabled = False
    yield
    settings.api_key_required = original_auth
    limiter.enabled = original_enabled


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
def engine(
    grid_mapper: GridMapper, mock_source: MockCarbonSource, cache: IntensityCache
) -> RoutingEngine:
    return RoutingEngine(carbon_source=mock_source, grid_mapper=grid_mapper, cache=cache)


@pytest.fixture
def client() -> TestClient:
    from carbon_mesh.main import app

    return TestClient(app)
