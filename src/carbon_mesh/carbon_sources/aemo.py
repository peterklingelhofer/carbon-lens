"""Australian Energy Market Operator (AEMO) — free, no API key required.

Covers 5 Australian NEM regions: NSW, QLD, VIC, SA, TAS.
Updates every 5 minutes.
"""

from datetime import datetime, timezone

from carbon_mesh.carbon_sources.http_pool import shared_client

from carbon_mesh.carbon_sources.emission_factors import (
    calculate_carbon_intensity,
    calculate_renewable_percentage,
)
from carbon_mesh.models.carbon import CarbonIntensity

API_URL = "https://visualisations.aemo.com.au/aemo/apps/api/report/5MIN"

AEMO_ZONES = {"AU-NSW", "AU-QLD", "AU-VIC", "AU-SA", "AU-TAS"}

# Map AEMO region IDs to our zone IDs
_REGION_MAP = {
    "NSW1": "AU-NSW",
    "QLD1": "AU-QLD",
    "VIC1": "AU-VIC",
    "SA1": "AU-SA",
    "TAS1": "AU-TAS",
}

# AEMO fuel type to normalized fuel type
_FUEL_MAP = {
    "black_coal": "coal",
    "brown_coal": "coal",
    "natural_gas": "natural_gas",
    "natural_gas_ccgt": "natural_gas",
    "natural_gas_ocgt": "natural_gas",
    "natural_gas_steam": "natural_gas",
    "kerosene": "petroleum",
    "diesel": "petroleum",
    "oil": "petroleum",
    "hydro": "hydro",
    "wind": "wind",
    "solar_utility": "solar",
    "solar_rooftop": "solar",
    "battery_discharging": "battery",
    "battery_charging": "battery",
    "biomass": "biomass",
    "geothermal": "geothermal",
    "other": "other",
}


class AEMOCarbonSource:
    def __init__(self) -> None:
        self._client = shared_client(timeout=10.0)

    def can_handle(self, grid_zone: str) -> bool:
        return grid_zone in AEMO_ZONES

    async def get_carbon_intensity(self, grid_zone: str) -> CarbonIntensity:
        results = await self.get_carbon_intensity_batch([grid_zone])
        if grid_zone not in results:
            raise ValueError(f"No AEMO data for zone: {grid_zone}")
        return results[grid_zone]

    async def get_carbon_intensity_batch(self, grid_zones: list[str]) -> dict[str, CarbonIntensity]:
        resp = await self._client.get(API_URL)
        resp.raise_for_status()
        data = resp.json()

        # Group generation by region
        region_fuel: dict[str, dict[str, float]] = {}
        for row in data.get("5MIN", []):
            aemo_region = row.get("REGIONID", "")
            zone = _REGION_MAP.get(aemo_region)
            if zone is None or zone not in grid_zones:
                continue
            fuel_type_raw = row.get("FUELTYPE", "other").lower().replace(" ", "_")
            normalized = _FUEL_MAP.get(fuel_type_raw, "other")
            mw = float(row.get("GENERATIONVALUE", 0) or 0)
            if zone not in region_fuel:
                region_fuel[zone] = {}
            region_fuel[zone][normalized] = region_fuel[zone].get(normalized, 0) + mw

        results: dict[str, CarbonIntensity] = {}
        now = datetime.now(timezone.utc)
        for zone in grid_zones:
            fuel_mix = region_fuel.get(zone)
            if not fuel_mix:
                continue
            results[zone] = CarbonIntensity(
                grid_zone=zone,
                carbon_intensity_gco2_kwh=round(calculate_carbon_intensity(fuel_mix), 1),
                renewable_percentage=round(calculate_renewable_percentage(fuel_mix), 1),
                timestamp=now,
                source="aemo",
            )

        return results
