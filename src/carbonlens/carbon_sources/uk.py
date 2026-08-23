"""UK Carbon Intensity API — free, no API key required.

Covers GB national + 17 regional zones (GB-1 to GB-17).
Docs: https://carbonintensity.org.uk/
"""

from datetime import UTC, datetime

import httpx

from carbonlens.carbon_sources.http_pool import shared_client
from carbonlens.models.carbon import CarbonIntensity

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
            # /intensity carries no mix, so fetch the national mix NESO publishes
            # alongside it rather than inferring the renewable share from intensity.
            renewable = await self._national_renewable_pct()
            return CarbonIntensity(
                grid_zone="GB",
                carbon_intensity_gco2_kwh=float(intensity),
                renewable_percentage=renewable,
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
                intensity = _region_intensity(region)
                return CarbonIntensity(
                    grid_zone=grid_zone,
                    carbon_intensity_gco2_kwh=float(intensity),
                    renewable_percentage=_renewable_or_zero(region),
                    timestamp=datetime.now(UTC),
                    source="uk_carbon_intensity",
                )

        raise ValueError(f"Region {region_id} not found in UK API response")

    async def _national_renewable_pct(self) -> float:
        """GB renewable share from NESO's published national mix.

        Falls back to 0.0 only if the mix is unavailable: understating renewables is
        the safe direction, where the old intensity-derived estimate overstated them
        by 47 points.
        """
        try:
            resp = await self._client.get("/generation")
            resp.raise_for_status()
            mix = resp.json()["data"]["generationmix"]
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            return 0.0
        return renewable_pct_from_mix(mix) or 0.0

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
                        intensity = _region_intensity(region)
                        results[zone] = CarbonIntensity(
                            grid_zone=zone,
                            carbon_intensity_gco2_kwh=float(intensity),
                            renewable_percentage=_renewable_or_zero(region),
                            timestamp=datetime.now(UTC),
                            source="uk_carbon_intensity",
                        )
            except (httpx.HTTPError, ValueError, KeyError):
                pass

        return results


# NESO fuel labels counted as renewable. Biomass is deliberately excluded, matching
# the treatment in the emission-factor corpus: it is combustion, and the biogenic-CO2
# accounting that would make it renewable is contested.
_RENEWABLE_FUELS = {"wind", "solar", "hydro"}


def renewable_pct_from_mix(generation_mix: list[dict]) -> float | None:
    """Renewable share from NESO's own published generation mix.

    Returns None when the mix is absent or empty, so the caller can decide rather
    than get a fabricated number.
    """
    if not generation_mix:
        return None
    total = 0.0
    renewable = 0.0
    for entry in generation_mix:
        try:
            pct = float(entry.get("perc") or 0)
        except (TypeError, ValueError):
            continue
        total += pct
        if entry.get("fuel") in _RENEWABLE_FUELS:
            renewable += pct
    if total <= 0:
        return None
    return round(min(100.0, renewable / total * 100), 1)


def _region_intensity(region: dict) -> float:
    """Intensity for one NESO region.

    The regional endpoint publishes only `forecast` and `index`; unlike the national
    endpoint it carries NO `actual` key. Indexing ["actual"] therefore raised
    KeyError for every one of the 17 regional zones, which the single-zone path
    propagated and the batch path swallowed -- so GB-1..GB-17 silently fell through
    the provider cascade to a weather estimate or mock while the README advertised
    18 live UK zones. See docs/VERIFICATION.md §6.
    """
    intensity = region.get("intensity") or {}
    value = intensity.get("actual")
    if value is None:
        value = intensity.get("forecast")
    if value is None:
        raise ValueError(f"NESO region {region.get('regionid')} reported no intensity")
    return float(value)


def _renewable_or_zero(region: dict) -> float:
    """Renewable share for one NESO region, 0.0 when the mix is missing."""
    return renewable_pct_from_mix(region.get("generationmix") or []) or 0.0


def _estimate_renewable_pct(intensity: float) -> float:
    """DEPRECATED, and measurably wrong. Retained only so the error stays visible.

    This inferred renewable share from carbon intensity on a straight line anchored
    at "450 gCO2/kWh = 0% renewable". Measured against NESO's own published
    generation mix over 97 half-hour settlement periods (2026-08-21 to 2026-08-23),
    it overstated the renewable share by a mean of **+46.9 percentage points**, and
    never once understated it. Its output ranged 60.7-87.8% while the truth ranged
    10.3-51.2%: the two ranges do not overlap at all.

    The cause is a system-boundary error. NESO's intensity is DIRECT combustion, so
    wind, solar, hydro and nuclear all score 0 and UK intensity is structurally far
    below 450; a 450 anchor therefore reads almost any UK half-hour as
    predominantly renewable. Nuclear-heavy periods are read as renewable for the
    same reason.

    Callers now use renewable_pct_from_mix(), which reads NESO's published mix from
    a response this module was already fetching. See docs/VERIFICATION.md §5.
    """
    if intensity <= 0:
        return 100.0
    pct = max(0.0, (1 - intensity / 450) * 100)
    return round(min(100.0, pct), 1)
