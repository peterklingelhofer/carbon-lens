"""GridStatus.io carbon source — uses real-time 5-minute fuel mix data.

Docs: https://docs.gridstatus.io/
Endpoint: GET /v1/datasets/{iso}_fuel_mix/query
"""

from datetime import datetime, timezone

import httpx

from carbon_mesh.carbon_sources.http_pool import shared_client

from carbon_mesh.carbon_sources.emission_factors import (
    GRIDSTATUS_FUEL_MAP,
    calculate_carbon_intensity,
    calculate_renewable_percentage,
)
from carbon_mesh.models.carbon import CarbonIntensity

API_BASE = "https://api.gridstatus.io/v1"

# Mapping from grid_zone to GridStatus ISO name (for dataset naming)
_GRID_ZONE_TO_ISO: dict[str, str] = {
    "US-MIDA-PJM": "pjm",
    "US-CAL-CISO": "caiso",
    "US-MIDW-MISO": "miso",
    "CA-ON": "ieso",
    "CA-QC": "ieso",
}

# ISOs where we have known fuel mix datasets
_SUPPORTED_ISOS = {"caiso", "ercot", "isone", "miso", "nyiso", "pjm", "spp", "ieso"}


class GridStatusCarbonSource:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = shared_client(
            base_url=API_BASE,
            headers={"x-api-key": api_key},
            timeout=15.0,
        )

    def _can_handle(self, grid_zone: str) -> bool:
        return grid_zone in _GRID_ZONE_TO_ISO

    async def get_carbon_intensity(self, grid_zone: str) -> CarbonIntensity:
        iso = _GRID_ZONE_TO_ISO.get(grid_zone)
        if not iso:
            raise ValueError(f"GridStatus does not cover grid zone: {grid_zone}")

        dataset = f"{iso}_fuel_mix"
        resp = await self._client.get(
            f"/datasets/{dataset}/query",
            params={
                "limit": 1,
                "sort": "interval_start_utc",
                "sort_dir": "desc",
                "json_schema": "array-of-arrays",
            },
        )
        resp.raise_for_status()
        body = resp.json()

        data_rows = body.get("data", [])
        if len(data_rows) < 2:
            raise ValueError(f"No GridStatus data for {dataset}")

        headers = data_rows[0]
        values = data_rows[1]
        row = dict(zip(headers, values))

        # Parse fuel mix from column names
        fuel_mix_mw: dict[str, float] = {}
        skip_cols = {
            "interval_start_utc",
            "interval_end_utc",
            "interval_start_local",
            "interval_end_local",
            "publish_time_utc",
        }
        for col, val in row.items():
            col_lower = col.lower().replace(" ", "_")
            if col_lower in skip_cols or val is None:
                continue
            normalized = GRIDSTATUS_FUEL_MAP.get(col_lower)
            if normalized is None:
                continue
            try:
                mw = float(val)
            except (ValueError, TypeError):
                continue
            fuel_mix_mw[normalized] = fuel_mix_mw.get(normalized, 0) + mw

        intensity = calculate_carbon_intensity(fuel_mix_mw)
        renewable_pct = calculate_renewable_percentage(fuel_mix_mw)

        # Parse timestamp
        ts_str = row.get("interval_start_utc", "")
        try:
            ts = datetime.fromisoformat(ts_str).replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            ts = datetime.now(timezone.utc)

        return CarbonIntensity(
            grid_zone=grid_zone,
            carbon_intensity_gco2_kwh=round(intensity, 1),
            renewable_percentage=round(renewable_pct, 1),
            timestamp=ts,
            source="gridstatus",
        )

    async def get_carbon_intensity_batch(self, grid_zones: list[str]) -> dict[str, CarbonIntensity]:
        results: dict[str, CarbonIntensity] = {}
        for zone in grid_zones:
            if not self._can_handle(zone):
                continue
            try:
                results[zone] = await self.get_carbon_intensity(zone)
            except (httpx.HTTPError, ValueError):
                pass
        return results
