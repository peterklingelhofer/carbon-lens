"""EIA API v2 carbon source — uses real-time hourly fuel mix data from Form EIA-930.

Docs: https://www.eia.gov/opendata/documentation.php
Endpoint: /v2/electricity/rto/fuel-type-data/data
"""

from datetime import datetime, timezone

from carbon_mesh.carbon_sources.http_pool import shared_client

from carbon_mesh.carbon_sources.emission_factors import (
    EIA_FUEL_MAP,
    calculate_carbon_intensity,
    calculate_renewable_percentage,
)
from carbon_mesh.models.carbon import CarbonIntensity

API_BASE = "https://api.eia.gov/v2"

# Mapping from grid_zone to EIA respondent code
_GRID_ZONE_TO_EIA: dict[str, str] = {
    "US-MIDA-PJM": "PJM",
    "US-CAL-CISO": "CISO",
    "US-NW-BPAT": "BPAT",
    "US-MIDW-MISO": "MISO",
    "US-SE-SOCO": "SOCO",
    "US-SW-NEVP": "NEVP",
    "US-SW-AZPS": "AZPS",
}


class EIACarbonSource:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = shared_client(base_url=API_BASE, timeout=15.0)

    def _can_handle(self, grid_zone: str) -> bool:
        return grid_zone in _GRID_ZONE_TO_EIA

    async def get_carbon_intensity(self, grid_zone: str) -> CarbonIntensity:
        respondent = _GRID_ZONE_TO_EIA.get(grid_zone)
        if not respondent:
            raise ValueError(f"EIA does not cover grid zone: {grid_zone}")

        resp = await self._client.get(
            "/electricity/rto/fuel-type-data/data",
            params={
                "api_key": self._api_key,
                "frequency": "hourly",
                "data[0]": "value",
                "sort[0][column]": "period",
                "sort[0][direction]": "desc",
                "length": 20,
                "facets[respondent][]": respondent,
            },
        )
        resp.raise_for_status()
        data = resp.json()

        rows = data.get("response", {}).get("data", [])
        if not rows:
            raise ValueError(f"No EIA data for respondent {respondent}")

        # Group by the most recent period
        latest_period = rows[0]["period"]
        fuel_mix_mw: dict[str, float] = {}
        for row in rows:
            if row["period"] != latest_period:
                break
            eia_code = row.get("fueltype", "OTH")
            normalized = EIA_FUEL_MAP.get(eia_code, "other")
            value = float(row.get("value") or 0)
            fuel_mix_mw[normalized] = fuel_mix_mw.get(normalized, 0) + value

        intensity = calculate_carbon_intensity(fuel_mix_mw)
        renewable_pct = calculate_renewable_percentage(fuel_mix_mw)

        # Parse period like "2026-03-11T06"
        try:
            ts = datetime.strptime(latest_period, "%Y-%m-%dT%H").replace(tzinfo=timezone.utc)
        except ValueError:
            ts = datetime.now(timezone.utc)

        return CarbonIntensity(
            grid_zone=grid_zone,
            carbon_intensity_gco2_kwh=round(intensity, 1),
            renewable_percentage=round(renewable_pct, 1),
            timestamp=ts,
            source="eia",
            grid_load_mw=round(sum(fuel_mix_mw.values())),
        )

    async def get_carbon_intensity_batch(self, grid_zones: list[str]) -> dict[str, CarbonIntensity]:
        # Collect all respondents we need
        respondents = set()
        zone_to_respondent: dict[str, str] = {}
        for zone in grid_zones:
            resp_id = _GRID_ZONE_TO_EIA.get(zone)
            if resp_id:
                respondents.add(resp_id)
                zone_to_respondent[zone] = resp_id

        if not respondents:
            return {}

        # Single batch request for all respondents
        params: list[tuple[str, str]] = [
            ("api_key", self._api_key),
            ("frequency", "hourly"),
            ("data[0]", "value"),
            ("sort[0][column]", "period"),
            ("sort[0][direction]", "desc"),
            ("length", str(len(respondents) * 15)),  # ~10 fuel types per respondent
        ]
        for r in respondents:
            params.append(("facets[respondent][]", r))

        resp = await self._client.get("/electricity/rto/fuel-type-data/data", params=params)
        resp.raise_for_status()
        data = resp.json()

        rows = data.get("response", {}).get("data", [])

        # Group by respondent → latest period → fuel mix
        respondent_fuel: dict[str, dict[str, float]] = {}
        respondent_period: dict[str, str] = {}
        for row in rows:
            r = row.get("respondent", "")
            period = row.get("period", "")
            if r not in respondent_period:
                respondent_period[r] = period
            if period != respondent_period[r]:
                continue  # Only use latest period per respondent
            eia_code = row.get("fueltype", "OTH")
            normalized = EIA_FUEL_MAP.get(eia_code, "other")
            value = float(row.get("value") or 0)
            if r not in respondent_fuel:
                respondent_fuel[r] = {}
            respondent_fuel[r][normalized] = respondent_fuel[r].get(normalized, 0) + value

        results: dict[str, CarbonIntensity] = {}
        for zone, resp_id in zone_to_respondent.items():
            fuel_mix = respondent_fuel.get(resp_id, {})
            if not fuel_mix:
                continue
            intensity = calculate_carbon_intensity(fuel_mix)
            renewable_pct = calculate_renewable_percentage(fuel_mix)
            period_str = respondent_period.get(resp_id, "")
            try:
                ts = datetime.strptime(period_str, "%Y-%m-%dT%H").replace(tzinfo=timezone.utc)
            except ValueError:
                ts = datetime.now(timezone.utc)
            results[zone] = CarbonIntensity(
                grid_zone=zone,
                carbon_intensity_gco2_kwh=round(intensity, 1),
                renewable_percentage=round(renewable_pct, 1),
                timestamp=ts,
                source="eia",
                grid_load_mw=round(sum(fuel_mix.values())),
            )

        return results
