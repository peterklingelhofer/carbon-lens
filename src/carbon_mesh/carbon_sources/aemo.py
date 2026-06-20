"""Australian NEM carbon data — free, no API key required.

Fuel-mix per NEM region (NSW, QLD, VIC, SA, TAS) comes from OpenElectricity
(api.openelectricity.org.au, formerly OpenNEM), which republishes AEMO dispatch
data with a per-fueltech breakdown. AEMO's own public ``5MIN`` report was
retired (now returns HTTP 204) and its replacement summary feed dropped the
fuel breakdown, so OpenElectricity is the parseable free source for the mix.

Updates every 5 minutes.
"""

from datetime import datetime, timezone

from carbon_mesh.carbon_sources.emission_factors import intensity_from_fuel_mix
from carbon_mesh.carbon_sources.http_pool import shared_client
from carbon_mesh.models.carbon import CarbonIntensity

# Per-region power, grouped by fuel-tech. One request returns every NEM region.
API_URL = (
    "https://api.openelectricity.org.au/v4/data/network/NEM"
    "?metrics=power&primary_grouping=network_region&secondary_grouping=fueltech_group"
)

AEMO_ZONES = {"AU-NSW", "AU-QLD", "AU-VIC", "AU-SA", "AU-TAS"}

# OpenElectricity region id -> our zone id
_REGION_MAP = {
    "NSW1": "AU-NSW",
    "QLD1": "AU-QLD",
    "VIC1": "AU-VIC",
    "SA1": "AU-SA",
    "TAS1": "AU-TAS",
}

# OpenElectricity fueltech_group -> normalized fuel. Storage/charging groups
# (battery*, pumps) are deliberately omitted: they're loads or net-zero stores
# and counting them would double-count or push the mix negative.
_FUELTECH_MAP = {
    "coal": "coal",
    "gas": "natural_gas",
    "distillate": "petroleum",
    "hydro": "hydro",
    "wind": "wind",
    "solar": "solar",
    "bioenergy": "biomass",
}


def _latest(points: list) -> float | None:
    """Most recent non-null MW value from a [[timestamp, value], ...] series."""
    for _, value in reversed(points or []):
        if value is not None:
            return float(value)
    return None


def region_fuel_from_oe(data: dict, grid_zones: list[str]) -> dict[str, dict[str, float]]:
    """Latest MW per (zone, normalized fuel) from an OpenElectricity power
    response grouped by network_region + fueltech_group."""
    region_fuel: dict[str, dict[str, float]] = {}
    for series in data.get("data", [{}])[0].get("results", []):
        cols = series.get("columns", {})
        zone = _REGION_MAP.get(cols.get("region", ""))
        fuel = _FUELTECH_MAP.get(cols.get("fueltech_group", ""))
        if zone is None or fuel is None or zone not in grid_zones:
            continue
        mw = _latest(series.get("data", []))
        if mw is None or mw <= 0:
            continue
        region_fuel.setdefault(zone, {})
        region_fuel[zone][fuel] = region_fuel[zone].get(fuel, 0) + mw
    return region_fuel


class AEMOCarbonSource:
    def __init__(self) -> None:
        self._client = shared_client(timeout=20.0)

    def can_handle(self, grid_zone: str) -> bool:
        return grid_zone in AEMO_ZONES

    async def get_carbon_intensity(self, grid_zone: str) -> CarbonIntensity:
        results = await self.get_carbon_intensity_batch([grid_zone])
        if grid_zone not in results:
            raise ValueError(f"No AEMO/OpenElectricity data for zone: {grid_zone}")
        return results[grid_zone]

    async def get_carbon_intensity_batch(self, grid_zones: list[str]) -> dict[str, CarbonIntensity]:
        resp = await self._client.get(API_URL, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        region_fuel = region_fuel_from_oe(resp.json(), grid_zones)

        results: dict[str, CarbonIntensity] = {}
        now = datetime.now(timezone.utc)
        for zone in grid_zones:
            fuel_mix = region_fuel.get(zone)
            if not fuel_mix:
                continue
            results[zone] = intensity_from_fuel_mix(zone, fuel_mix, "openelectricity", now)

        return results
