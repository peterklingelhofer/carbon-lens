"""Optional MEASURED marginal source (bring your own key).

By default CarbonLens reports a HEURISTIC marginal intensity (merit-order estimate
from the live fuel mix). When an operator supplies a WattTime token AND a grid-zone
-> WattTime-region map, this fetches WattTime's measured marginal operating emissions
rate (MOER) and the signal uses it instead, clearly labelled "measured". Off by
default; unmapped zones stay on the heuristic. The operator provides the mapping, so
we never guess a region code (which would risk reporting the wrong grid's number).
"""

from __future__ import annotations

import httpx

from carbon_mesh.carbon_sources.http_pool import shared_client

# WattTime MOER is in lbs CO2 / MWh. Convert to g CO2 / kWh:
#   1 lb = 453.59237 g;  1 MWh = 1000 kWh.
_LBS_PER_MWH_TO_G_PER_KWH = 453.59237 / 1000


def moer_to_gco2_kwh(lbs_per_mwh: float) -> float:
    """Convert a WattTime MOER (lbs CO2/MWh) to g CO2/kWh."""
    return round(lbs_per_mwh * _LBS_PER_MWH_TO_G_PER_KWH, 1)


def parse_zone_map(spec: str) -> dict[str, str]:
    """Parse ``"GRIDZONE:REGION,GRIDZONE:REGION"`` into a dict; ignores malformed pairs."""
    out: dict[str, str] = {}
    for pair in spec.split(","):
        zone, sep, region = pair.partition(":")
        if sep and zone.strip() and region.strip():
            out[zone.strip()] = region.strip()
    return out


class WattTimeMarginalSource:
    """Measured marginal (MOER) from WattTime v3, for the zones an operator has mapped."""

    def __init__(self, token: str, zone_map: dict[str, str]) -> None:
        self._token = token
        self._zone_map = zone_map
        self._client = shared_client(timeout=10.0)

    def can_handle(self, grid_zone: str) -> bool:
        return grid_zone in self._zone_map

    async def marginal_intensity(self, grid_zone: str) -> float | None:
        """Current measured marginal for a mapped zone (g CO2/kWh), or None."""
        region = self._zone_map.get(grid_zone)
        if not region:
            return None
        try:
            resp = await self._client.get(
                "https://api.watttime.org/v3/forecast",
                params={"region": region, "signal_type": "co2_moer"},
                headers={"Authorization": f"Bearer {self._token}"},
            )
            resp.raise_for_status()
            data = resp.json().get("data", [])
        except (httpx.HTTPError, ValueError, KeyError):
            return None
        if not data:
            return None
        value = data[0].get("value")
        return moer_to_gco2_kwh(float(value)) if value is not None else None


def marginal_source_from_settings(settings) -> WattTimeMarginalSource | None:
    """Build the configured marginal source, or None when not enabled."""
    if not settings.watttime_token:
        return None
    zone_map = parse_zone_map(settings.watttime_zone_map)
    if not zone_map:
        return None
    return WattTimeMarginalSource(settings.watttime_token, zone_map)
