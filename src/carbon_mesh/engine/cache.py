import asyncio
import logging
import time
from typing import Awaitable, Callable

from carbon_mesh.models.carbon import CarbonIntensity

logger = logging.getLogger(__name__)


class IntensityCache:
    """In-memory cache with stale-while-revalidate semantics.

    Entries within ``ttl_seconds`` are fresh — returned immediately.
    Entries between ``ttl_seconds`` and ``2 * ttl_seconds`` are stale —
    returned immediately while a background task refreshes them.
    Entries older than ``2 * ttl_seconds`` are expired and block on a fetch.
    """

    def __init__(self, ttl_seconds: int = 300) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, CarbonIntensity]] = {}
        # Track which zones are currently being refreshed to avoid duplicate fetches
        self._refreshing: set[str] = set()

    def _age(self, zone: str, now: float) -> float | None:
        """Return age in seconds of a cached entry, or None if missing."""
        if zone not in self._store:
            return None
        return now - self._store[zone][0]

    async def get_or_fetch(
        self,
        zone: str,
        fetcher: Callable[[str], Awaitable[CarbonIntensity]],
    ) -> CarbonIntensity:
        now = time.monotonic()
        age = self._age(zone, now)

        # Fresh hit
        if age is not None and age < self._ttl:
            return self._store[zone][1]

        # Stale hit — return immediately, refresh in background
        if age is not None and age < self._ttl * 2:
            self._schedule_refresh_single(zone, fetcher)
            return self._store[zone][1]

        # Miss or expired — block on fetch
        value = await fetcher(zone)
        self._store[zone] = (time.monotonic(), value)
        return value

    async def get_or_fetch_batch(
        self,
        zones: list[str],
        batch_fetcher: Callable[[list[str]], Awaitable[dict[str, CarbonIntensity]]],
    ) -> dict[str, CarbonIntensity]:
        now = time.monotonic()
        results: dict[str, CarbonIntensity] = {}
        missing: list[str] = []
        stale: list[str] = []

        for zone in zones:
            age = self._age(zone, now)
            if age is not None and age < self._ttl:
                # Fresh
                results[zone] = self._store[zone][1]
            elif age is not None and age < self._ttl * 2:
                # Stale — use cached value, mark for background refresh
                results[zone] = self._store[zone][1]
                stale.append(zone)
            else:
                # Miss or expired
                missing.append(zone)

        # Fetch missing zones (blocking — we have no data to return)
        if missing:
            fetched = await batch_fetcher(missing)
            fetch_time = time.monotonic()
            for zone, value in fetched.items():
                self._store[zone] = (fetch_time, value)
                results[zone] = value

        # Refresh stale zones in the background
        if stale:
            self._schedule_refresh_batch(stale, batch_fetcher)

        return results

    def _schedule_refresh_single(
        self,
        zone: str,
        fetcher: Callable[[str], Awaitable[CarbonIntensity]],
    ) -> None:
        if zone in self._refreshing:
            return
        self._refreshing.add(zone)

        async def _refresh() -> None:
            try:
                value = await fetcher(zone)
                self._store[zone] = (time.monotonic(), value)
                logger.debug("SWR refresh for %s", zone)
            except Exception as e:
                logger.debug("SWR refresh failed for %s: %s", zone, e)
            finally:
                self._refreshing.discard(zone)

        asyncio.ensure_future(_refresh())

    def _schedule_refresh_batch(
        self,
        zones: list[str],
        batch_fetcher: Callable[[list[str]], Awaitable[dict[str, CarbonIntensity]]],
    ) -> None:
        to_refresh = [z for z in zones if z not in self._refreshing]
        if not to_refresh:
            return
        self._refreshing.update(to_refresh)

        async def _refresh() -> None:
            try:
                fetched = await batch_fetcher(to_refresh)
                fetch_time = time.monotonic()
                for zone, value in fetched.items():
                    self._store[zone] = (fetch_time, value)
                if fetched:
                    logger.debug("SWR batch refresh: %d zones", len(fetched))
            except Exception as e:
                logger.debug("SWR batch refresh failed: %s", e)
            finally:
                self._refreshing.difference_update(to_refresh)

        asyncio.ensure_future(_refresh())

    def invalidate(self, zone: str | None = None) -> None:
        if zone is None:
            self._store.clear()
        else:
            self._store.pop(zone, None)
