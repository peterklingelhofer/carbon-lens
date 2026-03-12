import time
from typing import Awaitable, Callable

from carbon_mesh.models.carbon import CarbonIntensity


class IntensityCache:
    def __init__(self, ttl_seconds: int = 300) -> None:
        self._ttl = ttl_seconds
        self._store: dict[str, tuple[float, CarbonIntensity]] = {}

    async def get_or_fetch(
        self,
        zone: str,
        fetcher: Callable[[str], Awaitable[CarbonIntensity]],
    ) -> CarbonIntensity:
        now = time.monotonic()
        if zone in self._store:
            stored_time, stored_value = self._store[zone]
            if now - stored_time < self._ttl:
                return stored_value

        value = await fetcher(zone)
        self._store[zone] = (now, value)
        return value

    async def get_or_fetch_batch(
        self,
        zones: list[str],
        batch_fetcher: Callable[[list[str]], Awaitable[dict[str, CarbonIntensity]]],
    ) -> dict[str, CarbonIntensity]:
        now = time.monotonic()
        results: dict[str, CarbonIntensity] = {}
        missing: list[str] = []

        for zone in zones:
            if zone in self._store:
                stored_time, stored_value = self._store[zone]
                if now - stored_time < self._ttl:
                    results[zone] = stored_value
                    continue
            missing.append(zone)

        if missing:
            fetched = await batch_fetcher(missing)
            fetch_time = time.monotonic()
            for zone, value in fetched.items():
                self._store[zone] = (fetch_time, value)
                results[zone] = value

        return results

    def invalidate(self, zone: str | None = None) -> None:
        if zone is None:
            self._store.clear()
        else:
            self._store.pop(zone, None)
