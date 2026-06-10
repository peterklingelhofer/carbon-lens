"""Snapshot-backed carbon source for the scheduler.

The scheduler evaluates dozens of zones per request. Fetching each one live made
the first request take ~40s. The published snapshot already holds the current
intensity for every zone in a single ~35 KB document (the same one the frontend
reads), so serve current readings from it -- one cached fetch instead of dozens
of upstream calls -- and fall back to the live source for anything missing.
"""

import time
from datetime import datetime

from carbon_mesh.carbon_sources.base import CarbonDataSource
from carbon_mesh.carbon_sources.http_pool import shared_client
from carbon_mesh.models.carbon import CarbonIntensity

# Snapshot refreshes every few minutes, so a short shared TTL is plenty.
_TTL_SECONDS = 180.0
_CACHE: dict[str, tuple[float, dict[str, CarbonIntensity]]] = {}


def zone_map_from_intensities(intensities: dict) -> dict[str, CarbonIntensity]:
    """Build {grid_zone: CarbonIntensity} from a snapshot's intensities block,
    keeping the first reading per zone (many regions share one zone)."""
    zone_map: dict[str, CarbonIntensity] = {}
    for entry in intensities.values():
        zone = entry.get("grid_zone")
        if not zone or zone in zone_map:
            continue
        try:
            zone_map[zone] = CarbonIntensity(
                grid_zone=zone,
                carbon_intensity_gco2_kwh=entry["carbon_intensity_gco2_kwh"],
                renewable_percentage=entry["renewable_percentage"],
                timestamp=datetime.fromisoformat(entry["timestamp"]),
                source=entry.get("source", "snapshot"),
                grid_load_mw=entry.get("grid_load_mw"),
            )
        except (KeyError, ValueError):
            continue
    return zone_map


class SnapshotBackedSource:
    def __init__(self, snapshot_url: str, fallback: CarbonDataSource) -> None:
        self._url = snapshot_url
        self._fallback = fallback
        self._client = shared_client(timeout=15.0)

    async def _zone_map(self) -> dict[str, CarbonIntensity]:
        """zone -> current intensity from the published snapshot, cached."""
        if not self._url:
            return {}
        cached = _CACHE.get(self._url)
        if cached and time.monotonic() - cached[0] < _TTL_SECONDS:
            return cached[1]
        try:
            resp = await self._client.get(self._url)
            resp.raise_for_status()
            intensities = resp.json().get("intensities", {})
        except Exception:
            return {}

        zone_map = zone_map_from_intensities(intensities)
        if zone_map:
            _CACHE[self._url] = (time.monotonic(), zone_map)
        return zone_map

    async def get_carbon_intensity(self, grid_zone: str) -> CarbonIntensity:
        zone_map = await self._zone_map()
        if grid_zone in zone_map:
            return zone_map[grid_zone]
        return await self._fallback.get_carbon_intensity(grid_zone)

    async def get_carbon_intensity_batch(self, grid_zones: list[str]) -> dict[str, CarbonIntensity]:
        zone_map = await self._zone_map()
        results = {z: zone_map[z] for z in grid_zones if z in zone_map}
        missing = [z for z in grid_zones if z not in zone_map]
        if missing:
            results.update(await self._fallback.get_carbon_intensity_batch(missing))
        return results
