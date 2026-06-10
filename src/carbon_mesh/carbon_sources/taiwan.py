"""Taiwan grid carbon data via Taipower's real-time per-unit generation feed.

Free, no API key. Taipower publishes every operating unit's current output with
a fuel label (Chinese + English); we sum by fuel and apply emission factors.
Updates roughly every 10 minutes.
"""

import json
import re
import ssl
from datetime import datetime, timezone

import httpx

from carbon_mesh.carbon_sources.emission_factors import (
    calculate_carbon_intensity,
    calculate_marginal_intensity,
    calculate_renewable_percentage,
)
from carbon_mesh.models.carbon import CarbonIntensity

API_URL = "https://www.taipower.com.tw/d006/loadGraph/loadGraph/data/genary.json"
TAIWAN_ZONES = {"TW"}

_TAG_RE = re.compile(r"<[^>]+>")

# Taipower's TLS cert omits the Subject Key Identifier extension, which Python's
# strict X.509 mode (default on 3.13+) rejects. Relax *only* that strict check
# -- chain and hostname verification stay on. The feed is public, read-only data.
_TLS = ssl.create_default_context()
_TLS.verify_flags &= ~getattr(ssl, "VERIFY_X509_STRICT", 0)

# Taipower returns an empty 202 unless the request looks like the dashboard's
# own XHR (Referer + X-Requested-With), so mirror those headers.
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Referer": "https://www.taipower.com.tw/tc/page.aspx?mid=206",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
}


def _fuel_of(label: str) -> str | None:
    """Map a Taipower fuel label to a normalized fuel, matching on the English
    name in parentheses (most stable). Returns None for rows to skip."""
    if "Load" in label:
        return None  # storage charging is a load, not generation
    if "Energy Storage" in label:
        return "battery"
    if "Coal" in label:
        return "coal"
    if "LNG" in label or "Co-Gen" in label:
        return "natural_gas"
    if "Fuel Oil" in label:
        return "oil"
    if "Nuclear" in label:
        return "nuclear"
    if "Solar" in label:
        return "solar"
    if "Wind" in label:
        return "wind"
    if "Hydro" in label:
        return "hydro"
    if "Other Renewable" in label:
        return "geothermal"  # geothermal/biomass mix -- counted renewable
    return "other"


def fuel_mix_from_rows(rows: list) -> dict[str, float]:
    """Sum Taipower per-unit generation rows into a normalized fuel mix (MW).

    Each row is [fuel-label-HTML, _, unit, capacity, generation, pct]; we read
    the fuel from the label and the MW from column 4.
    """
    fuel_mix: dict[str, float] = {}
    for r in rows:
        if len(r) < 5:
            continue
        fuel = _fuel_of(_TAG_RE.sub("", r[0]))
        if fuel is None:
            continue
        try:
            mw = float(r[4])
        except (TypeError, ValueError):
            continue
        if mw <= 0:
            continue
        fuel_mix[fuel] = fuel_mix.get(fuel, 0) + mw
    return fuel_mix


class TaiwanCarbonSource:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(timeout=15.0, verify=_TLS, headers=_HEADERS)

    def can_handle(self, grid_zone: str) -> bool:
        return grid_zone in TAIWAN_ZONES

    async def get_carbon_intensity(self, grid_zone: str) -> CarbonIntensity:
        results = await self.get_carbon_intensity_batch([grid_zone])
        if grid_zone not in results:
            raise ValueError(f"No Taipower data for zone: {grid_zone}")
        return results[grid_zone]

    async def get_carbon_intensity_batch(self, grid_zones: list[str]) -> dict[str, CarbonIntensity]:
        if "TW" not in grid_zones:
            return {}
        resp = await self._client.get(API_URL)
        resp.raise_for_status()
        # Served with a UTF-8 BOM and a text/html content-type, so decode and
        # parse explicitly rather than relying on resp.json().
        rows = json.loads(resp.content.decode("utf-8-sig")).get("aaData", [])

        fuel_mix = fuel_mix_from_rows(rows)
        if sum(fuel_mix.values()) <= 0:
            return {}
        return {
            "TW": CarbonIntensity(
                grid_zone="TW",
                carbon_intensity_gco2_kwh=round(calculate_carbon_intensity(fuel_mix), 1),
                renewable_percentage=round(calculate_renewable_percentage(fuel_mix), 1),
                timestamp=datetime.now(timezone.utc),
                source="taipower",
                grid_load_mw=round(sum(fuel_mix.values())),
                marginal_intensity_gco2_kwh=round(calculate_marginal_intensity(fuel_mix), 1),
            )
        }
