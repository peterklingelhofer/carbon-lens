"""ENTSO-E Transparency Platform provider — requires free security token.

Covers 36+ European countries/bidding zones.
Docs: https://transparency.entsoe.eu/content/static_content/Static%20content/web%20api/Guide.html
"""

from datetime import datetime, timezone, timedelta

from carbon_mesh.carbon_sources.base import SingleZoneCarbonSource
from carbon_mesh.carbon_sources.http_pool import ENTSOE_SEMAPHORE, get_with_retry, shared_client
from carbon_mesh.carbon_sources.xml_safe import entsoe_ns, safe_parse_xml

from carbon_mesh.carbon_sources.emission_factors import intensity_from_fuel_mix
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
    "B01": "biomass",  # Biomass
    "B02": "coal",  # Fossil Brown coal/Lignite
    "B04": "natural_gas",  # Fossil Gas
    "B05": "coal",  # Fossil Hard coal
    "B06": "petroleum",  # Fossil Oil
    "B07": "petroleum",  # Fossil Oil shale
    "B08": "other",  # Fossil Peat
    "B09": "geothermal",  # Geothermal
    "B10": "hydro",  # Hydro Pumped Storage
    "B11": "hydro",  # Hydro Run-of-river and poundage
    "B12": "hydro",  # Hydro Water Reservoir
    "B13": "other",  # Marine
    "B14": "nuclear",  # Nuclear
    "B15": "other",  # Other renewable
    "B16": "solar",  # Solar
    "B17": "other",  # Waste
    "B18": "wind",  # Wind Offshore
    "B19": "wind",  # Wind Onshore
    "B20": "other",  # Other
}


class ENTSOECarbonSource(SingleZoneCarbonSource):
    def __init__(self, security_token: str) -> None:
        self._token = security_token
        self._client = shared_client(timeout=15.0)

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

        resp = await get_with_retry(
            self._client,
            API_URL,
            params={
                "securityToken": self._token,
                "documentType": "A75",  # Actual generation per type
                "processType": "A16",  # Realised
                "in_Domain": eic,
                "periodStart": period_start,
                "periodEnd": period_end,
            },
            semaphore=ENTSOE_SEMAPHORE,
        )
        resp.raise_for_status()

        fuel_mix = self._parse_generation_xml(resp.text)
        if not fuel_mix:
            raise ValueError(f"No generation data for {grid_zone}")

        return intensity_from_fuel_mix(grid_zone, fuel_mix, "entsoe", now)

    def _parse_generation_xml(self, xml_text: str) -> dict[str, float]:
        """Parse ENTSO-E XML response into fuel mix dict."""
        fuel_mix: dict[str, float] = {}
        root = safe_parse_xml(xml_text)
        if root is None:
            return fuel_mix
        ns = entsoe_ns(root)

        for ts in root.findall(".//ns:TimeSeries", ns):
            psr_type_elem = ts.find(".//ns:MktPSRType/ns:psrType", ns)
            if psr_type_elem is None:
                continue
            psr_type = psr_type_elem.text or ""
            normalized = _PRODUCTION_TYPE_MAP.get(psr_type, "other")

            # Last point is the most recent
            points = ts.findall(".//ns:Point", ns)
            if points:
                qty_elem = points[-1].find("ns:quantity", ns)
                if qty_elem is not None and qty_elem.text:
                    fuel_mix[normalized] = fuel_mix.get(normalized, 0) + float(qty_elem.text)

        return fuel_mix
