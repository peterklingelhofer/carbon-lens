"""UK Carbon Intensity API — free, no API key required.

Covers GB national + 17 regional zones (GB-1 to GB-17).
Docs: https://carbonintensity.org.uk/
"""

from datetime import UTC, datetime

import httpx

from carbon_mesh.carbon_sources.http_pool import shared_client
from carbon_mesh.models.carbon import CarbonIntensity

API_BASE = "https://api.carbonintensity.org.uk"

# Zones this provider handles
UK_ZONES = {"GB"} | {f"GB-{i}" for i in range(1, 18)}

# Map our zone IDs to the API's regionid
_ZONE_TO_REGION_ID: dict[str, int] = {f"GB-{i}": i for i in range(1, 18)}


class UKCarbonSource:
    def __init__(self) -> None:
        self._client = shared_client(base_url=API_BASE, timeout=10.0)

    def can_handle(self, grid_zone: str) -> bool:
        return grid_zone in UK_ZONES

    async def get_carbon_intensity(self, grid_zone: str) -> CarbonIntensity:
        if grid_zone == "GB":
            resp = await self._client.get("/intensity")
            resp.raise_for_status()
            data = resp.json()["data"][0]
            intensity = data["intensity"]["actual"] or data["intensity"]["forecast"]
            return CarbonIntensity(
                grid_zone="GB",
                carbon_intensity_gco2_kwh=float(intensity),
                renewable_percentage=_estimate_renewable_pct(float(intensity)),
                timestamp=datetime.fromisoformat(data["from"]).replace(tzinfo=UTC),
                source="uk_carbon_intensity",
            )

        region_id = _ZONE_TO_REGION_ID.get(grid_zone)
        if region_id is None:
            raise ValueError(f"Unknown UK zone: {grid_zone}")

        resp = await self._client.get("/regional")
        resp.raise_for_status()
        regions = resp.json()["data"][0]["regions"]
        for region in regions:
            if region["regionid"] == region_id:
                intensity = region["intensity"]["actual"] or region["intensity"]["forecast"]
                return CarbonIntensity(
                    grid_zone=grid_zone,
                    carbon_intensity_gco2_kwh=float(intensity),
                    renewable_percentage=_estimate_renewable_pct(float(intensity)),
                    timestamp=datetime.now(UTC),
                    source="uk_carbon_intensity",
                )

        raise ValueError(f"Region {region_id} not found in UK API response")

    async def get_carbon_intensity_batch(self, grid_zones: list[str]) -> dict[str, CarbonIntensity]:
        results: dict[str, CarbonIntensity] = {}

        # Check if we need national
        needs_national = "GB" in grid_zones
        needs_regional = any(z.startswith("GB-") for z in grid_zones)

        if needs_national:
            try:
                results["GB"] = await self.get_carbon_intensity("GB")
            except (httpx.HTTPError, ValueError, KeyError):
                pass

        if needs_regional:
            try:
                resp = await self._client.get("/regional")
                resp.raise_for_status()
                regions = resp.json()["data"][0]["regions"]
                for region in regions:
                    zone = f"GB-{region['regionid']}"
                    if zone in grid_zones:
                        intensity = region["intensity"]["actual"] or region["intensity"]["forecast"]
                        results[zone] = CarbonIntensity(
                            grid_zone=zone,
                            carbon_intensity_gco2_kwh=float(intensity),
                            renewable_percentage=_estimate_renewable_pct(float(intensity)),
                            timestamp=datetime.now(UTC),
                            source="uk_carbon_intensity",
                        )
            except (httpx.HTTPError, ValueError, KeyError):
                pass

        return results


def _estimate_renewable_pct(intensity: float) -> float:
    """Estimate renewable percentage from carbon intensity.

    UK grid: ~0 gCO2/kWh = 100% renewable, ~450+ = 0% renewable.
    """
    if intensity <= 0:
        return 100.0
    pct = max(0.0, (1 - intensity / 450) * 100)
    return round(min(100.0, pct), 1)
