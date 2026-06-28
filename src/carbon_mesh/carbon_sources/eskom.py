"""Eskom South Africa provider — heuristic estimate, no API key required.

Covers 1 zone: ZA (South Africa national grid).
South Africa's grid is ~85% coal, making it one of the dirtiest in the world.

NOTE: This is a static time-of-day heuristic, not a live grid feed. Eskom does
not publish a free real-time fuel-mix / carbon-intensity API, so this returns a
modeled estimate tagged `source="eskom_heuristic"`. Treat it as illustrative.
"""

from datetime import UTC, datetime

from carbon_mesh.carbon_sources.base import SingleZoneCarbonSource
from carbon_mesh.models.carbon import CarbonIntensity

ESKOM_ZONES = {"ZA"}


class EskomCarbonSource(SingleZoneCarbonSource):
    def can_handle(self, grid_zone: str) -> bool:
        return grid_zone in ESKOM_ZONES

    async def get_carbon_intensity(self, grid_zone: str) -> CarbonIntensity:
        if grid_zone != "ZA":
            raise ValueError(f"Unknown Eskom zone: {grid_zone}")
        return self._heuristic()

    def _heuristic(self) -> CarbonIntensity:
        """Time-of-day heuristic for the South African grid: ~85% coal plus small
        nuclear (Koeberg), wind, solar, and hydro, base intensity ~780 gCO2/kWh.
        """
        base_intensity = 780.0
        base_renewable = 8.0

        # SAST = UTC+2
        now = datetime.now(UTC)
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
            timestamp=datetime.now(UTC),
            source="eskom_heuristic",
        )
