"""Optional MEASURED marginal source (bring your own key).

By default CarbonLens reports a HEURISTIC marginal intensity (merit-order estimate
from the live fuel mix). When an operator supplies a WattTime token AND a grid-zone
-> WattTime-region map, this fetches WattTime's measured marginal operating emissions
rate (MOER) and the signal uses it instead, clearly labelled "measured". Off by
default; unmapped zones stay on the heuristic. The operator provides the mapping, so
we never guess a region code (which would risk reporting the wrong grid's number).
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from carbon_mesh.carbon_sources.http_pool import shared_client

# WattTime MOER is in lbs CO2 / MWh. Convert to g CO2 / kWh:
#   1 lb = 453.59237 g;  1 MWh = 1000 kWh.
_LBS_PER_MWH_TO_G_PER_KWH = 453.59237 / 1000


def moer_to_gco2_kwh(lbs_per_mwh: float) -> float:
    """Convert a WattTime MOER (lbs CO2/MWh) to g CO2/kWh."""
    return round(lbs_per_mwh * _LBS_PER_MWH_TO_G_PER_KWH, 1)


def _parse_forecast(
    data: list[dict],
    now: datetime,
    hours: int,
    *,
    time_key: str,
    value_key: str,
    convert,
) -> dict[int, float]:
    """Turn provider forecast points into ``{hour_offset: g CO2/kWh}`` from ``now``.

    time_key / value_key name the per-point fields; convert maps a raw value to
    g CO2/kWh. Pure, so parsing and conversion are testable without the network.
    """
    curve: dict[int, float] = {}
    for pt in data:
        t, v = pt.get(time_key), pt.get(value_key)
        if not t or v is None:
            continue
        try:
            ts = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        offset = round((ts - now).total_seconds() / 3600)
        if 0 <= offset <= hours:
            curve[offset] = convert(float(v))
    return curve


def parse_moer_forecast(data: list[dict], now: datetime, hours: int) -> dict[int, float]:
    """WattTime points (``{"point_time", "value": lbs/MWh}``) into a g CO2/kWh curve."""
    return _parse_forecast(
        data, now, hours, time_key="point_time", value_key="value", convert=moer_to_gco2_kwh
    )


def parse_zone_map(spec: str) -> dict[str, str]:
    """Parse ``"GRIDZONE:REGION,GRIDZONE:REGION"`` into a dict; ignores malformed pairs."""
    out: dict[str, str] = {}
    for pair in spec.split(","):
        zone, sep, region = pair.partition(":")
        if sep and zone.strip() and region.strip():
            out[zone.strip()] = region.strip()
    return out


class _MeasuredMarginalSource:
    """Shared scaffolding for a token + zone-map measured-marginal provider.

    Subclasses supply the endpoint, headers, and per-payload parsing; the base
    holds the credentials, zone gate, and the request/error template.
    """

    def __init__(self, token: str, zone_map: dict[str, str]) -> None:
        self._token = token
        self._zone_map = zone_map
        self._client = shared_client(timeout=10.0)

    def can_handle(self, grid_zone: str) -> bool:
        return grid_zone in self._zone_map

    async def _get(self, url: str, params: dict, headers: dict) -> dict | None:
        """GET returning parsed JSON, or None on any network/decode failure."""
        try:
            resp = await self._client.get(url, params=params, headers=headers)
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError, KeyError):
            return None


class WattTimeMarginalSource(_MeasuredMarginalSource):
    """Measured marginal (MOER) from WattTime v3, for the zones an operator has mapped."""

    _URL = "https://api.watttime.org/v3/forecast"

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}

    async def marginal_intensity(self, grid_zone: str) -> float | None:
        """Current measured marginal for a mapped zone (g CO2/kWh), or None."""
        region = self._zone_map.get(grid_zone)
        if not region:
            return None
        body = await self._get(
            self._URL,
            params={"region": region, "signal_type": "co2_moer"},
            headers=self._headers(),
        )
        data = (body or {}).get("data", [])
        if not data:
            return None
        value = data[0].get("value")
        return moer_to_gco2_kwh(float(value)) if value is not None else None

    async def marginal_forecast(self, grid_zone: str, hours: int) -> dict[int, float]:
        """Measured marginal forecast for a mapped zone: ``{hour_offset: g CO2/kWh}``."""
        region = self._zone_map.get(grid_zone)
        if not region:
            return {}
        body = await self._get(
            self._URL,
            params={"region": region, "signal_type": "co2_moer", "horizon_hours": hours},
            headers=self._headers(),
        )
        if body is None:
            return {}
        return parse_moer_forecast(body.get("data", []), datetime.now(timezone.utc), hours)


def parse_em_forecast(data: list[dict], now: datetime, hours: int) -> dict[int, float]:
    """Electricity Maps points (``{"datetime", "marginalCarbonIntensity": g/kWh}``,
    already g/kWh) into a g CO2/kWh curve."""
    return _parse_forecast(
        data,
        now,
        hours,
        time_key="datetime",
        value_key="marginalCarbonIntensity",
        convert=lambda v: round(v, 1),
    )


class ElectricityMapsMarginalSource(_MeasuredMarginalSource):
    """Measured marginal from Electricity Maps (gCO2eq/kWh directly), for mapped zones.

    Their marginal endpoints are commercial, so this only runs when an operator
    supplies their own token AND an explicit zone map.
    """

    _BASE = "https://api.electricitymap.org/v3/marginal-carbon-intensity"

    def _headers(self) -> dict:
        return {"auth-token": self._token}

    async def marginal_intensity(self, grid_zone: str) -> float | None:
        zone = self._zone_map.get(grid_zone)
        if not zone:
            return None
        body = await self._get(
            f"{self._BASE}/latest", params={"zone": zone}, headers=self._headers()
        )
        if body is None:
            return None
        value = body.get("marginalCarbonIntensity")
        return round(float(value), 1) if value is not None else None

    async def marginal_forecast(self, grid_zone: str, hours: int) -> dict[int, float]:
        zone = self._zone_map.get(grid_zone)
        if not zone:
            return {}
        body = await self._get(
            f"{self._BASE}/forecast", params={"zone": zone}, headers=self._headers()
        )
        if body is None:
            return {}
        return parse_em_forecast(body.get("forecast", []), datetime.now(timezone.utc), hours)


# Either measured-marginal provider; both share the can_handle / marginal_intensity /
# marginal_forecast shape that the signal and scheduler duck-type on.
MarginalSource = WattTimeMarginalSource | ElectricityMapsMarginalSource


def marginal_source_from_settings(settings):
    """Build the configured measured-marginal source, or None. WattTime wins over
    Electricity Maps; both need the operator's own token AND an explicit zone map.
    """
    wt_map = parse_zone_map(getattr(settings, "watttime_zone_map", ""))
    if getattr(settings, "watttime_token", "") and wt_map:
        return WattTimeMarginalSource(settings.watttime_token, wt_map)
    em_map = parse_zone_map(getattr(settings, "electricity_maps_zone_map", ""))
    if em_map and getattr(settings, "electricity_maps_api_key", ""):
        return ElectricityMapsMarginalSource(settings.electricity_maps_api_key, em_map)
    return None


def marginal_unmapped(settings) -> bool:
    """True when a marginal credential is set but no zone is mapped, so no source
    builds and the signal silently stays heuristic, a misconfiguration worth alerting on.
    """
    if marginal_source_from_settings(settings) is not None:
        return False
    wt = bool(getattr(settings, "watttime_token", "")) and not parse_zone_map(
        getattr(settings, "watttime_zone_map", "")
    )
    em = bool(getattr(settings, "electricity_maps_api_key", "")) and not parse_zone_map(
        getattr(settings, "electricity_maps_zone_map", "")
    )
    return bool(wt or em)
