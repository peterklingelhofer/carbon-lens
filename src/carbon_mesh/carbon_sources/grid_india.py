"""Grid India provider — free, no API key required.

Covers 5 Indian power grid regions: Northern, Southern, Eastern, Western, North-Eastern.
Data from Grid India real-time reports.
"""

from datetime import UTC, datetime

from carbon_mesh.carbon_sources.base import SingleZoneCarbonSource
from carbon_mesh.carbon_sources.http_pool import shared_client
from carbon_mesh.carbon_sources.mock import _MOCK_DATA
from carbon_mesh.models.carbon import CarbonIntensity

INDIA_ZONES = {"IN-NO", "IN-SO", "IN-EA", "IN-WE", "IN-NE"}

# (intensity gCO2/kWh, renewable_pct) per region, read from the canonical mock
# table so the heuristic baseline can't drift from it. India's grid is ~70% coal
_REGION_DEFAULTS: dict[str, tuple[float, float]] = {z: _MOCK_DATA[z] for z in INDIA_ZONES}

API_URL = "https://report.grid-india.in/api/data/current-generation"


class GridIndiaCarbonSource(SingleZoneCarbonSource):
    def __init__(self) -> None:
        self._client = shared_client(timeout=10.0)

    def can_handle(self, grid_zone: str) -> bool:
        return grid_zone in INDIA_ZONES

    async def get_carbon_intensity(self, grid_zone: str) -> CarbonIntensity:
        if grid_zone not in INDIA_ZONES:
            raise ValueError(f"Unknown India zone: {grid_zone}")

        # Try to fetch real data
        try:
            return await self._fetch_live(grid_zone)
        except Exception:
            # Fall back to heuristic with time-of-day adjustment
            return self._heuristic(grid_zone)

    async def _fetch_live(self, grid_zone: str) -> CarbonIntensity:
        resp = await self._client.get(API_URL)
        resp.raise_for_status()
        data = resp.json()

        region_key = {
            "IN-NO": "Northern",
            "IN-SO": "Southern",
            "IN-EA": "Eastern",
            "IN-WE": "Western",
            "IN-NE": "North-Eastern",
        }.get(grid_zone)

        region_data = None
        for entry in data.get("data", data if isinstance(data, list) else []):
            if isinstance(entry, dict) and entry.get("region") == region_key:
                region_data = entry
                break

        if region_data is None:
            raise ValueError("Region not found in Grid India response")

        thermal = float(region_data.get("thermal", 0) or 0)
        hydro = float(region_data.get("hydro", 0) or 0)
        nuclear = float(region_data.get("nuclear", 0) or 0)
        renewable = float(region_data.get("renewable", 0) or 0)
        total = thermal + hydro + nuclear + renewable
        if total == 0:
            raise ValueError("Zero total generation")

        # Thermal is mostly coal in India (~820 gCO2/kWh)
        intensity = (thermal * 820) / total
        renewable_pct = ((hydro + renewable) / total) * 100

        return CarbonIntensity(
            grid_zone=grid_zone,
            carbon_intensity_gco2_kwh=round(intensity, 1),
            renewable_percentage=round(renewable_pct, 1),
            timestamp=datetime.now(UTC),
            source="grid_india",
        )

    def _heuristic(self, grid_zone: str) -> CarbonIntensity:
        """Time-of-day adjusted heuristic for Indian grid."""
        base_intensity, base_renewable = _REGION_DEFAULTS.get(grid_zone, (600, 20))

        # Solar zones get cleaner during daytime (IST = UTC+5:30)
        now = datetime.now(UTC)
        ist_hour = (now.hour + 5) % 24  # Rough IST
        if 10 <= ist_hour <= 16:
            # Peak solar hours — reduce intensity
            base_intensity *= 0.75
            base_renewable = min(100, base_renewable * 1.5)
        elif ist_hour < 6 or ist_hour > 20:
            # Night — more coal
            base_intensity *= 1.1
            base_renewable *= 0.7

        return CarbonIntensity(
            grid_zone=grid_zone,
            carbon_intensity_gco2_kwh=round(base_intensity, 1),
            renewable_percentage=round(base_renewable, 1),
            timestamp=datetime.now(UTC),
            source="grid_india_heuristic",
        )
