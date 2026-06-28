"""EIA API v2 carbon source — uses real-time hourly fuel mix data from Form EIA-930.

Docs: https://www.eia.gov/opendata/documentation.php
Endpoint: /v2/electricity/rto/fuel-type-data/data
"""

import asyncio
from datetime import UTC, datetime

from carbon_mesh.carbon_sources.emission_factors import EIA_FUEL_MAP, intensity_from_fuel_mix
from carbon_mesh.carbon_sources.http_pool import shared_client
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
    "US-TEX-ERCO": "ERCO",
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

        latest_period = rows[0]["period"]
        fuel_mix_mw: dict[str, float] = {}
        for row in rows:
            if row["period"] != latest_period:
                break
            eia_code = row.get("fueltype", "OTH")
            normalized = EIA_FUEL_MAP.get(eia_code, "other")
            value = float(row.get("value") or 0)
            fuel_mix_mw[normalized] = fuel_mix_mw.get(normalized, 0) + value

        try:
            ts = datetime.strptime(latest_period, "%Y-%m-%dT%H").replace(tzinfo=UTC)
        except ValueError:
            ts = datetime.now(UTC)

        return intensity_from_fuel_mix(grid_zone, fuel_mix_mw, "eia", ts)

    async def get_carbon_intensity_batch(self, grid_zones: list[str]) -> dict[str, CarbonIntensity]:
        # Group the requested zones by EIA respondent (multiple cloud regions can
        # share one respondent, e.g. us-east-1 and eastus both map to PJM).
        zones_by_respondent: dict[str, list[str]] = {}
        for zone in grid_zones:
            respondent_id = _GRID_ZONE_TO_EIA.get(zone)
            if respondent_id:
                zones_by_respondent.setdefault(respondent_id, []).append(zone)

        if not zones_by_respondent:
            return {}

        # One request per respondent, concurrently. A single combined request
        # sorted by period is length-capped, so respondents reporting on time
        # crowd out any whose EIA-930 fuel-mix reporting lags (PJM/MISO/SOCO can
        # run a day-plus behind), silently dropping them. Per-respondent fetches
        # each one's own latest period regardless of how far behind it is.
        respondents = list(zones_by_respondent.keys())

        async def fetch(respondent_id: str) -> tuple[str, CarbonIntensity]:
            # Reuse the single-zone path (correct latest-period handling); the
            # representative zone only seeds the request, then we fan the reading
            # back out to every zone on this respondent below.
            zone = zones_by_respondent[respondent_id][0]
            return respondent_id, await self.get_carbon_intensity(zone)

        settled = await asyncio.gather(*(fetch(r) for r in respondents), return_exceptions=True)

        results: dict[str, CarbonIntensity] = {}
        for item in settled:
            if isinstance(item, BaseException):
                continue
            respondent_id, intensity = item
            for zone in zones_by_respondent[respondent_id]:
                results[zone] = intensity.model_copy(update={"grid_zone": zone})

        return results
