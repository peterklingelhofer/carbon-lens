"""ENTSO-E Transparency Platform provider — requires free security token.

Covers 36+ European countries/bidding zones.
Docs: https://transparency.entsoe.eu/content/static_content/Static%20content/web%20api/Guide.html
"""

from datetime import datetime, timezone, timedelta
from xml.etree import ElementTree

import httpx

from carbon_mesh.carbon_sources.emission_factors import (
    calculate_carbon_intensity,
    calculate_renewable_percentage,
)
from carbon_mesh.models.carbon import CarbonIntensity

API_URL = "https://web-api.tp.entsoe.eu/api"

# ENTSO-E bidding zone → EIC code
ENTSOE_ZONE_MAP: dict[str, str] = {
    "DE": "10Y1001A1001A83F",
    "FR": "10YFR-RTE------C",
    "ES": "10YES-REE------0",
    "PT": "10YPT-REN------W",
    "NL": "10YNL----------L",
    "BE": "10YBE----------2",
    "AT": "10YAT-APG------L",
    "CH": "10YCH-SWISSGRIDZ",
    "PL": "10YPL-AREA-----S",
    "CZ": "10YCZ-CEPS-----N",
    "DK-DK1": "10YDK-1--------W",
    "DK-DK2": "10YDK-2--------M",
    "FI": "10YFI-1--------U",
    "SE-SE1": "10Y1001A1001A44P",
    "SE-SE2": "10Y1001A1001A45N",
    "SE-SE3": "10Y1001A1001A46L",
    "SE-SE4": "10Y1001A1001A47J",
    "NO-NO1": "10YNO-1--------2",
    "NO-NO2": "10YNO-2--------T",
    "NO-NO3": "10YNO-3--------J",
    "NO-NO4": "10YNO-4--------9",
    "NO-NO5": "10YNO-5--------O",
    "IE": "10Y1001A1001A59C",
    "IT-NO": "10Y1001A1001A73I",
    "GR": "10YGR-HTSO-----Y",
    "RO": "10YRO-TEL------P",
    "BG": "10YCA-BULGARIA-R",
    "HU": "10YHU-MAVIR----U",
    "SK": "10YSK-SEPS-----K",
    "HR": "10YHR-HEP------M",
    "RS": "10YCS-SERBIATSOV",
    "SI": "10YSI-ELES-----O",
    "BA": "10YBA-JPCC-----D",
    "ME": "10YCS-CG-TSO---S",
    "MK": "10YMK-MEPSO----8",
    "AL": "10YAL-KESH-----5",
    "EE": "10Y1001A1001A39I",
    "LV": "10YLV-1001A00074",
    "LT": "10YLT-1001A0008Q",
}

ENTSOE_ZONES = set(ENTSOE_ZONE_MAP.keys())

# ENTSO-E production type → normalized fuel
_PRODUCTION_TYPE_MAP = {
    "B01": "biomass",        # Biomass
    "B02": "coal",           # Fossil Brown coal/Lignite
    "B04": "natural_gas",    # Fossil Gas
    "B05": "coal",           # Fossil Hard coal
    "B06": "petroleum",      # Fossil Oil
    "B07": "petroleum",      # Fossil Oil shale
    "B08": "other",          # Fossil Peat
    "B09": "geothermal",     # Geothermal
    "B10": "hydro",          # Hydro Pumped Storage
    "B11": "hydro",          # Hydro Run-of-river and poundage
    "B12": "hydro",          # Hydro Water Reservoir
    "B13": "other",          # Marine
    "B14": "nuclear",        # Nuclear
    "B15": "other",          # Other renewable
    "B16": "solar",          # Solar
    "B17": "other",          # Waste
    "B18": "wind",           # Wind Offshore
    "B19": "wind",           # Wind Onshore
    "B20": "other",          # Other
}


class ENTSOECarbonSource:
    def __init__(self, security_token: str) -> None:
        self._token = security_token
        self._client = httpx.AsyncClient(timeout=15.0)

    def can_handle(self, grid_zone: str) -> bool:
        return grid_zone in ENTSOE_ZONES

    async def get_carbon_intensity(self, grid_zone: str) -> CarbonIntensity:
        eic = ENTSOE_ZONE_MAP.get(grid_zone)
        if not eic:
            raise ValueError(f"Unknown ENTSO-E zone: {grid_zone}")

        # Request actual generation per type for the last hour
        now = datetime.now(timezone.utc)
        period_start = (now - timedelta(hours=1)).strftime("%Y%m%d%H00")
        period_end = now.strftime("%Y%m%d%H00")

        resp = await self._client.get(
            API_URL,
            params={
                "securityToken": self._token,
                "documentType": "A75",  # Actual generation per type
                "processType": "A16",   # Realised
                "in_Domain": eic,
                "periodStart": period_start,
                "periodEnd": period_end,
            },
        )
        resp.raise_for_status()

        fuel_mix = self._parse_generation_xml(resp.text)
        if not fuel_mix:
            raise ValueError(f"No generation data for {grid_zone}")

        return CarbonIntensity(
            grid_zone=grid_zone,
            carbon_intensity_gco2_kwh=round(calculate_carbon_intensity(fuel_mix), 1),
            renewable_percentage=round(calculate_renewable_percentage(fuel_mix), 1),
            timestamp=now,
            source="entsoe",
        )

    def _parse_generation_xml(self, xml_text: str) -> dict[str, float]:
        """Parse ENTSO-E XML response into fuel mix dict."""
        fuel_mix: dict[str, float] = {}
        try:
            root = ElementTree.fromstring(xml_text)
            ns = {"ns": "urn:iec62325.351:tc57wg16:451-6:generationloaddocument:3:0"}

            for ts in root.findall(".//ns:TimeSeries", ns):
                psr_type_elem = ts.find(".//ns:MktPSRType/ns:psrType", ns)
                if psr_type_elem is None:
                    continue
                psr_type = psr_type_elem.text or ""
                normalized = _PRODUCTION_TYPE_MAP.get(psr_type, "other")

                # Get the last point (most recent)
                points = ts.findall(".//ns:Point", ns)
                if points:
                    last_point = points[-1]
                    qty_elem = last_point.find("ns:quantity", ns)
                    if qty_elem is not None and qty_elem.text:
                        mw = float(qty_elem.text)
                        fuel_mix[normalized] = fuel_mix.get(normalized, 0) + mw
        except ElementTree.ParseError:
            pass

        return fuel_mix

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
