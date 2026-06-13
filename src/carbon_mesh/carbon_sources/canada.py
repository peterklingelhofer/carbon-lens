"""Canadian grid carbon data — free, no API key required.

Three provinces, three very different public feeds:
  CA-ON  IESO    generation-by-fuel hourly XML (reports-public.ieso.ca)
  CA-AB  AESO    Current Supply Demand HTML report (ets.aeso.ca)
  CA-QC  (est.)  Hydro-Québec is ~99% hydro with no clean real-time fuel feed,
                 so it's a fixed low-carbon estimate rather than a measurement.
"""

import asyncio
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from carbon_mesh.carbon_sources.emission_factors import (
    calculate_carbon_intensity,
    calculate_marginal_intensity,
    calculate_renewable_percentage,
    power_breakdown,
)
from carbon_mesh.carbon_sources.http_pool import shared_client
from carbon_mesh.carbon_sources.xml_safe import parse_xml
from carbon_mesh.models.carbon import CarbonIntensity

CANADA_ZONES = {"CA-ON", "CA-AB", "CA-QC"}

IESO_URL = (
    "https://reports-public.ieso.ca/public/GenOutputbyFuelHourly/PUB_GenOutputbyFuelHourly.xml"
)
AESO_URL = "http://ets.aeso.ca/ets_web/ip/Market/Reports/CSDReportServlet?contentType=html"

_IESO_FUEL_MAP = {
    "NUCLEAR": "nuclear",
    "GAS": "natural_gas",
    "HYDRO": "hydro",
    "WIND": "wind",
    "SOLAR": "solar",
    "BIOFUEL": "biomass",
}

_AESO_FUEL_MAP = {
    "COAL": "coal",
    # Alberta reports gas under several plant-type labels, all gas-fired.
    "GAS": "natural_gas",
    "COGENERATION": "natural_gas",
    "COMBINED CYCLE": "natural_gas",
    "SIMPLE CYCLE": "natural_gas",
    "GAS FIRED STEAM": "natural_gas",
    "DUAL FUEL": "natural_gas",
    "HYDRO": "hydro",
    "WIND": "wind",
    "SOLAR": "solar",
    "ENERGY STORAGE": "battery",
    "OTHER": "other",
}

# AESO summary rows: <TR><TD>FUEL</TD><TD>MC</TD><TD>TNG</TD><TD>DCR</TD></TR>
# (MC = max capability, TNG = total net generation = what we want, DCR = reserve).
_AESO_ROW = re.compile(
    r"<TR>\s*<TD>([A-Z][A-Z ]+?)</TD>\s*<TD>(\d+)</TD>\s*<TD>(\d+)</TD>\s*<TD>(\d+)</TD>\s*</TR>"
)


def _localname(el: ET.Element) -> str:
    return el.tag.rsplit("}", 1)[-1]


def ieso_fuel_mix(xml: bytes) -> dict[str, float]:
    """Latest-hour generation-by-fuel (MW) from IESO's GenOutputbyFuelHourly XML.
    Returns {} if no hour has generation."""
    root = parse_xml(xml)
    dailies = [e for e in root.iter() if _localname(e) == "DailyData"]
    if not dailies:
        return {}
    hours = [e for e in dailies[-1].iter() if _localname(e) == "HourlyData"]
    for hourly in reversed(hours):  # latest hour with generation wins
        fuel_mix: dict[str, float] = {}
        for ft in (e for e in hourly.iter() if _localname(e) == "FuelTotal"):
            fuel = next((c for c in ft.iter() if _localname(c) == "Fuel"), None)
            out = next((c for c in ft.iter() if _localname(c) == "Output"), None)
            norm = (
                _IESO_FUEL_MAP.get((fuel.text or "").strip().upper()) if fuel is not None else None
            )
            if norm is None or out is None:
                continue
            fuel_mix[norm] = fuel_mix.get(norm, 0) + float(out.text or 0)
        if sum(fuel_mix.values()) > 0:
            return fuel_mix
    return {}


def aeso_fuel_mix(html: str) -> dict[str, float]:
    """Generation-by-fuel (MW, the TNG column) from AESO's Current Supply Demand
    HTML summary. Returns {} if nothing parsed."""
    fuel_mix: dict[str, float] = {}
    for name, _mc, tng, _dcr in _AESO_ROW.findall(html):
        norm = _AESO_FUEL_MAP.get(name.strip())
        if norm is None:
            continue
        fuel_mix[norm] = fuel_mix.get(norm, 0) + float(tng)
    return fuel_mix if sum(fuel_mix.values()) > 0 else {}


class CanadaCarbonSource:
    def __init__(self) -> None:
        # IESO's by-fuel XML is several MB, so allow a generous read timeout.
        self._client = shared_client(timeout=30.0)

    def can_handle(self, grid_zone: str) -> bool:
        return grid_zone in CANADA_ZONES

    async def get_carbon_intensity(self, grid_zone: str) -> CarbonIntensity:
        if grid_zone == "CA-ON":
            return await self._ieso()
        if grid_zone == "CA-AB":
            return await self._aeso()
        if grid_zone == "CA-QC":
            return self._quebec()
        raise ValueError(f"Canada source does not cover zone: {grid_zone}")

    async def get_carbon_intensity_batch(self, grid_zones: list[str]) -> dict[str, CarbonIntensity]:
        wanted = [z for z in grid_zones if z in CANADA_ZONES]
        settled = await asyncio.gather(
            *(self.get_carbon_intensity(z) for z in wanted), return_exceptions=True
        )
        return {z: r for z, r in zip(wanted, settled) if isinstance(r, CarbonIntensity)}

    async def _ieso(self) -> CarbonIntensity:
        resp = await self._client.get(IESO_URL)
        resp.raise_for_status()
        fuel_mix = ieso_fuel_mix(resp.content)
        if not fuel_mix:
            raise ValueError("IESO: no hour with generation")
        return self._build("CA-ON", fuel_mix, "ieso")

    async def _aeso(self) -> CarbonIntensity:
        resp = await self._client.get(AESO_URL, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        fuel_mix = aeso_fuel_mix(resp.text)
        if not fuel_mix:
            raise ValueError("AESO: no generation parsed")
        return self._build("CA-AB", fuel_mix, "aeso")

    def _quebec(self) -> CarbonIntensity:
        # Hydro-Québec is ~99% hydro/wind. No clean real-time fuel feed, so this
        # is an honest fixed estimate (flagged via the _heuristic source suffix).
        return CarbonIntensity(
            grid_zone="CA-QC",
            carbon_intensity_gco2_kwh=30.0,
            renewable_percentage=95.0,
            timestamp=datetime.now(timezone.utc),
            source="hydro_quebec_heuristic",
            grid_load_mw=None,
        )

    def _build(self, zone: str, fuel_mix: dict[str, float], source: str) -> CarbonIntensity:
        return CarbonIntensity(
            grid_zone=zone,
            carbon_intensity_gco2_kwh=round(calculate_carbon_intensity(fuel_mix), 1),
            renewable_percentage=round(calculate_renewable_percentage(fuel_mix), 1),
            timestamp=datetime.now(timezone.utc),
            source=source,
            grid_load_mw=round(sum(fuel_mix.values())),
            marginal_intensity_gco2_kwh=round(calculate_marginal_intensity(fuel_mix), 1),
            power_breakdown_mw=power_breakdown(fuel_mix),
        )
