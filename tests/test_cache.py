"""Tests for IntensityCache with stale-while-revalidate semantics."""

import asyncio
import time

import pytest

from carbon_mesh.engine.cache import IntensityCache
from carbon_mesh.models.carbon import CarbonIntensity


def _make_intensity(zone: str, value: float = 100.0) -> CarbonIntensity:
    from datetime import datetime, timezone

    return CarbonIntensity(
        grid_zone=zone,
        carbon_intensity_gco2_kwh=value,
        renewable_percentage=50.0,
        timestamp=datetime.now(timezone.utc),
        source="test",
    )


@pytest.fixture
def cache() -> IntensityCache:
    return IntensityCache(ttl_seconds=1)


@pytest.mark.asyncio
async def test_fresh_hit(cache: IntensityCache):
    """Fresh entries are returned without calling the fetcher again."""
    calls = 0

    async def fetcher(zone: str) -> CarbonIntensity:
        nonlocal calls
        calls += 1
        return _make_intensity(zone)

    result1 = await cache.get_or_fetch("Z1", fetcher)
    result2 = await cache.get_or_fetch("Z1", fetcher)
    assert result1.grid_zone == "Z1"
    assert result2.grid_zone == "Z1"
    assert calls == 1  # Second call served from cache


@pytest.mark.asyncio
async def test_expired_entry_blocks(cache: IntensityCache):
    """Entries older than 2x TTL trigger a blocking fetch."""
    call_values = [100.0, 200.0]
    call_idx = 0

    async def fetcher(zone: str) -> CarbonIntensity:
        nonlocal call_idx
        val = call_values[call_idx]
        call_idx += 1
        return _make_intensity(zone, val)

    result1 = await cache.get_or_fetch("Z1", fetcher)
    assert result1.carbon_intensity_gco2_kwh == 100.0

    # Simulate expiration (> 2x TTL)
    cache._store["Z1"] = (time.monotonic() - 3, cache._store["Z1"][1])

    result2 = await cache.get_or_fetch("Z1", fetcher)
    assert result2.carbon_intensity_gco2_kwh == 200.0


@pytest.mark.asyncio
async def test_stale_returns_cached_and_refreshes(cache: IntensityCache):
    """Stale entries return immediately and schedule a background refresh."""
    refresh_called = asyncio.Event()

    async def fetcher(zone: str) -> CarbonIntensity:
        refresh_called.set()
        return _make_intensity(zone, 999.0)

    # Seed cache
    cache._store["Z1"] = (time.monotonic(), _make_intensity("Z1", 100.0))

    # Make it stale (between TTL and 2*TTL)
    cache._store["Z1"] = (time.monotonic() - 1.5, cache._store["Z1"][1])

    result = await cache.get_or_fetch("Z1", fetcher)
    # Should return stale value immediately
    assert result.carbon_intensity_gco2_kwh == 100.0

    # Wait for background refresh
    await asyncio.wait_for(refresh_called.wait(), timeout=2.0)
    # Cache should now be updated
    assert cache._store["Z1"][1].carbon_intensity_gco2_kwh == 999.0


@pytest.mark.asyncio
async def test_batch_fresh_no_fetch(cache: IntensityCache):
    """Batch with all-fresh entries skips the fetcher."""
    calls = 0

    async def batch_fetcher(zones: list[str]) -> dict[str, CarbonIntensity]:
        nonlocal calls
        calls += 1
        return {z: _make_intensity(z) for z in zones}

    # Seed cache
    for z in ["A", "B", "C"]:
        cache._store[z] = (time.monotonic(), _make_intensity(z))

    results = await cache.get_or_fetch_batch(["A", "B", "C"], batch_fetcher)
    assert len(results) == 3
    assert calls == 0


@pytest.mark.asyncio
async def test_batch_missing_fetched(cache: IntensityCache):
    """Batch fetches missing zones and returns them."""

    async def batch_fetcher(zones: list[str]) -> dict[str, CarbonIntensity]:
        return {z: _make_intensity(z, 42.0) for z in zones}

    results = await cache.get_or_fetch_batch(["X", "Y"], batch_fetcher)
    assert results["X"].carbon_intensity_gco2_kwh == 42.0
    assert results["Y"].carbon_intensity_gco2_kwh == 42.0


@pytest.mark.asyncio
async def test_batch_stale_returns_and_refreshes(cache: IntensityCache):
    """Batch with stale entries returns cached values and refreshes in background."""
    refresh_called = asyncio.Event()

    async def batch_fetcher(zones: list[str]) -> dict[str, CarbonIntensity]:
        refresh_called.set()
        return {z: _make_intensity(z, 999.0) for z in zones}

    # Seed stale entries
    stale_time = time.monotonic() - 1.5
    for z in ["A", "B"]:
        cache._store[z] = (stale_time, _make_intensity(z, 50.0))

    results = await cache.get_or_fetch_batch(["A", "B"], batch_fetcher)
    # Returns stale values immediately
    assert results["A"].carbon_intensity_gco2_kwh == 50.0
    assert results["B"].carbon_intensity_gco2_kwh == 50.0

    # Background refresh should happen
    await asyncio.wait_for(refresh_called.wait(), timeout=2.0)


@pytest.mark.asyncio
async def test_invalidate_single(cache: IntensityCache):
    """Invalidating a single zone removes it from cache."""
    cache._store["Z1"] = (time.monotonic(), _make_intensity("Z1"))
    cache.invalidate("Z1")
    assert "Z1" not in cache._store


@pytest.mark.asyncio
async def test_invalidate_all(cache: IntensityCache):
    """Invalidating all zones clears the cache."""
    cache._store["A"] = (time.monotonic(), _make_intensity("A"))
    cache._store["B"] = (time.monotonic(), _make_intensity("B"))
    cache.invalidate()
    assert len(cache._store) == 0


@pytest.mark.asyncio
async def test_refresh_deduplication(cache: IntensityCache):
    """Multiple stale hits for the same zone only trigger one refresh."""
    call_count = 0

    async def fetcher(zone: str) -> CarbonIntensity:
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.1)
        return _make_intensity(zone, 999.0)

    # Seed stale
    cache._store["Z1"] = (time.monotonic() - 1.5, _make_intensity("Z1"))

    # Two stale reads
    await cache.get_or_fetch("Z1", fetcher)
    await cache.get_or_fetch("Z1", fetcher)

    # Let refresh complete
    await asyncio.sleep(0.3)
    assert call_count == 1  # Only one refresh
