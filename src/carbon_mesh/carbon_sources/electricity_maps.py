from datetime import datetime, timezone

import httpx

from carbon_mesh.carbon_sources.http_pool import shared_client

from carbon_mesh.models.carbon import CarbonIntensity

API_BASE = "https://api.electricitymap.org/v3"


class ElectricityMapsCarbonSource:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = shared_client(
            base_url=API_BASE,
            headers={"auth-token": api_key},
            timeout=10.0,
        )

    async def get_carbon_intensity(self, grid_zone: str) -> CarbonIntensity:
        resp = await self._client.get("/carbon-intensity/latest", params={"zone": grid_zone})
        resp.raise_for_status()
        data = resp.json()

        # Also fetch power breakdown for renewable percentage
        renewable_pct = 0.0
        try:
            power_resp = await self._client.get(
                "/power-breakdown/latest", params={"zone": grid_zone}
            )
            power_resp.raise_for_status()
            power_data = power_resp.json()
            renewable_pct = power_data.get("renewablePercentage", 0.0)
        except httpx.HTTPError:
            pass

        return CarbonIntensity(
            grid_zone=grid_zone,
            carbon_intensity_gco2_kwh=data["carbonIntensity"],
            renewable_percentage=renewable_pct,
            timestamp=datetime.fromisoformat(data["datetime"]),
            source="electricity_maps",
        )

    async def get_carbon_intensity_batch(self, grid_zones: list[str]) -> dict[str, CarbonIntensity]:
        results = {}
        for zone in grid_zones:
            try:
                results[zone] = await self.get_carbon_intensity(zone)
            except httpx.HTTPError:
                # Skip zones that fail — caller handles missing data
                results[zone] = CarbonIntensity(
                    grid_zone=zone,
                    carbon_intensity_gco2_kwh=999,
                    renewable_percentage=0,
                    timestamp=datetime.now(timezone.utc),
                    source="electricity_maps_error",
                )
        return results
