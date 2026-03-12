"""Open-Meteo weather-based carbon estimation — free, no API key required.

Uses real-time solar irradiance and wind speed to estimate renewable energy potential.
Works for any lat/lon worldwide — used as the ultimate fallback.
Docs: https://open-meteo.com/
"""

from datetime import datetime, timezone

import httpx

from carbon_mesh.carbon_sources.http_pool import shared_client
from carbon_mesh.models.carbon import CarbonIntensity

API_URL = "https://api.open-meteo.com/v1/forecast"

# Coordinates for grid zones not covered by other providers
ZONE_COORDINATES: dict[str, tuple[float, float]] = {
    # Asia-Pacific
    "JP-TK": (35.7, 139.7),
    "JP-CB": (35.2, 137.0),
    "JP-KN": (34.7, 135.5),
    "JP-KY": (33.6, 130.4),
    "KR": (37.6, 127.0),
    "SG": (1.4, 103.8),
    "TW": (25.0, 121.5),
    "HK": (22.3, 114.2),
    "TH": (13.8, 100.5),
    "VN": (21.0, 105.9),
    "PH": (14.6, 121.0),
    "ID": (-6.2, 106.8),
    "MY": (3.1, 101.7),
    # Middle East
    "AE": (25.3, 55.3),
    "SA": (24.7, 46.7),
    "IL": (32.1, 34.8),
    "TR": (41.0, 29.0),
    # Africa
    "KE": (-1.3, 36.8),
    "NG": (6.5, 3.4),
    "EG": (30.0, 31.2),
    "MA": (33.6, -7.6),
    # Americas
    "UY": (-34.9, -56.2),
    "PY": (-25.3, -57.6),
    "CR": (9.9, -84.1),
    "CL-SEN": (-33.4, -70.7),
    "AR": (-34.6, -58.4),
    "CO": (4.6, -74.1),
    "MX": (19.4, -99.1),
    # Oceania
    "NZ-NZN": (-36.9, 174.8),
    "NZ-NZS": (-43.5, 172.6),
    # Europe (fallback when ENTSO-E unavailable)
    "IS": (64.1, -21.9),
    "IE": (53.3, -6.3),
    "GB": (51.5, -0.1),
    "DE": (50.1, 8.7),
    "FR": (48.9, 2.3),
    "NL": (52.4, 4.9),
    "BE": (50.8, 4.4),
    "SE-SE3": (59.3, 18.1),
    "NO-NO1": (60.4, 5.3),
    "FI": (60.2, 24.9),
    "CH": (47.4, 8.5),
    "ES": (40.4, -3.7),
    "PT": (38.7, -9.1),
    "IT-NO": (45.5, 9.2),
    "PL": (52.2, 21.0),
    "AT": (48.2, 16.4),
}

# Typical grid base carbon intensity for regions (when weather data isn't available)
# This represents the non-weather-dependent fossil baseline
_BASELINE_INTENSITY: dict[str, float] = {
    "IS": 15,  # Iceland — almost all geothermal + hydro
    "NO-NO1": 20,
    "SE-SE3": 25,
    "FR": 60,
    "CH": 30,
    "NZ-NZN": 100,
    "NZ-NZS": 100,
    "UY": 50,
    "CR": 40,
    "PY": 20,  # Almost all hydro (Itaipu)
}


class OpenMeteoCarbonSource:
    def __init__(self) -> None:
        self._client = shared_client(timeout=10.0)

    def can_handle(self, grid_zone: str) -> bool:
        return grid_zone in ZONE_COORDINATES

    async def get_carbon_intensity(self, grid_zone: str) -> CarbonIntensity:
        coords = ZONE_COORDINATES.get(grid_zone)
        if not coords:
            raise ValueError(f"No coordinates for zone: {grid_zone}")

        lat, lon = coords
        resp = await self._client.get(
            API_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current_weather": "true",
                "hourly": "shortwave_radiation,windspeed_10m",
                "forecast_days": 1,
            },
        )
        resp.raise_for_status()
        data = resp.json()

        # Get current weather
        current = data.get("current_weather", {})
        wind_speed = current.get("windspeed", 0)

        # Get current hour's solar radiation
        hourly = data.get("hourly", {})
        solar_radiation = 0
        times = hourly.get("time", [])
        radiations = hourly.get("shortwave_radiation", [])
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:00")
        for i, t in enumerate(times):
            if t == now_str and i < len(radiations):
                solar_radiation = radiations[i] or 0
                break

        # Estimate renewable contribution from weather
        # Solar: 0-1000 W/m² → 0-40% grid penetration
        solar_pct = min(40, (solar_radiation / 1000) * 40)
        # Wind: 0-50 km/h → 0-30% grid penetration (cut-in ~12 km/h, rated ~45 km/h)
        wind_pct = 0
        if wind_speed > 12:
            wind_pct = min(30, ((wind_speed - 12) / 33) * 30)

        renewable_pct = min(100, solar_pct + wind_pct)

        # Use baseline if known, otherwise estimate from weather
        baseline = _BASELINE_INTENSITY.get(grid_zone, 350)
        # Higher renewables → lower intensity
        intensity = baseline * (1 - renewable_pct / 150)
        intensity = max(10, intensity)

        return CarbonIntensity(
            grid_zone=grid_zone,
            carbon_intensity_gco2_kwh=round(intensity, 1),
            renewable_percentage=round(renewable_pct, 1),
            timestamp=datetime.now(timezone.utc),
            source="open_meteo",
        )

    async def get_carbon_intensity_batch(
        self, grid_zones: list[str]
    ) -> dict[str, CarbonIntensity]:
        results: dict[str, CarbonIntensity] = {}
        for zone in grid_zones:
            if self.can_handle(zone):
                try:
                    results[zone] = await self.get_carbon_intensity(zone)
                except (httpx.HTTPError, ValueError):
                    pass
        return results
