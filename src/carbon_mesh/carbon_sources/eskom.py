"""Eskom South Africa provider — free, no API key required.

Covers 1 zone: ZA (South Africa national grid).
South Africa's grid is ~85% coal, making it one of the dirtiest in the world.
"""

from datetime import datetime, timezone

import httpx

from carbon_mesh.models.carbon import CarbonIntensity

ESKOM_ZONES = {"ZA"}

# Eskom API endpoint for current supply
API_URL = "https://developer.sepush.co.za/business/2.0/status"


class EskomCarbonSource:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=10.0)

    def can_handle(self, grid_zone: str) -> bool:
        return grid_zone in ESKOM_ZONES

    async def get_carbon_intensity(self, grid_zone: str) -> CarbonIntensity:
        if grid_zone != "ZA":
            raise ValueError(f"Unknown Eskom zone: {grid_zone}")

        # South Africa's grid is extremely coal-heavy (~85%)
        # Use heuristic with time-of-day solar adjustment
        return self._heuristic()

    def _heuristic(self) -> CarbonIntensity:
        """Heuristic for South African grid.

        SA is ~85% coal, with small amounts of nuclear (Koeberg),
        wind, solar, and hydro. Base intensity ~780 gCO2/kWh.
        """
        base_intensity = 780.0
        base_renewable = 8.0

        # SAST = UTC+2
        now = datetime.now(timezone.utc)
        sast_hour = (now.hour + 2) % 24

        # Midday solar helps slightly
        if 10 <= sast_hour <= 15:
            base_intensity *= 0.92
            base_renewable = 14.0
        elif sast_hour < 5 or sast_hour > 21:
            # Night — pure coal + nuclear
            base_intensity *= 1.02
            base_renewable = 5.0

        return CarbonIntensity(
            grid_zone="ZA",
            carbon_intensity_gco2_kwh=round(base_intensity, 1),
            renewable_percentage=round(base_renewable, 1),
            timestamp=datetime.now(timezone.utc),
            source="eskom_heuristic",
        )

    async def get_carbon_intensity_batch(
        self, grid_zones: list[str]
    ) -> dict[str, CarbonIntensity]:
        results: dict[str, CarbonIntensity] = {}
        for zone in grid_zones:
            if self.can_handle(zone):
                results[zone] = await self.get_carbon_intensity(zone)
        return results
