"""Day-ahead carbon forecast for European zones from ENTSO-E's free forecasts.

Combines the day-ahead wind+solar generation forecast (documentType A69) with
the day-ahead total-load forecast (A65) to derive, per hour, the forecasted
variable-renewable share of demand. The scheduler scales each region's current
carbon intensity by how that share changes versus now -- a real forecast signal
rather than a fixed daily curve. EU bidding zones only; needs the free token.
"""

import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from carbon_mesh.carbon_sources.entsoe import ENTSOE_ZONE_MAP
from carbon_mesh.carbon_sources.http_pool import ENTSOE_SEMAPHORE, get_with_retry, shared_client
from carbon_mesh.carbon_sources.xml_safe import parse_xml

API_URL = "https://web-api.tp.entsoe.eu/api"

# Wind onshore (B19), wind offshore (B18), solar (B16) -- the variable renewables
# ENTSO-E publishes a day-ahead forecast for.
_VRE_PSR = {"B16", "B18", "B19"}

# Day-ahead forecasts refresh ~hourly, so cache each zone's absolute-hour series
# across requests. Keyed by zone (not offset) so it stays valid as "now" moves
# within the TTL, and shared process-wide (the source is built per request).
_SERIES_TTL_SECONDS = 1800.0
_SERIES_CACHE: dict[str, tuple[float, dict[datetime, float]]] = {}


def _series_by_hour(xml_text: str, psr_filter: set[str] | None) -> dict[datetime, float]:
    """Parse an ENTSO-E forecast document into {hour(UTC): MW}.

    psr_filter limits to specific production types (generation docs); pass None
    for load documents. Sub-hourly resolutions are averaged within the hour, and
    multiple matching TimeSeries (e.g. wind + solar) are summed per hour.
    """
    try:
        root = parse_xml(xml_text)
    except Exception:
        return {}
    ns = {"ns": root.tag.split("}")[0].strip("{")}

    totals: dict[datetime, float] = defaultdict(float)
    for ts in root.findall(".//ns:TimeSeries", ns):
        if psr_filter is not None:
            psr = ts.find(".//ns:MktPSRType/ns:psrType", ns)
            if psr is None or (psr.text or "") not in psr_filter:
                continue
        for period in ts.findall(".//ns:Period", ns):
            start_el = period.find(".//ns:timeInterval/ns:start", ns)
            res_el = period.find("ns:resolution", ns)
            if start_el is None or start_el.text is None or res_el is None:
                continue
            start = datetime.fromisoformat(start_el.text.replace("Z", "+00:00"))
            step = 15 if res_el.text == "PT15M" else 60
            buckets: dict[datetime, list[float]] = defaultdict(list)
            for pt in period.findall("ns:Point", ns):
                pos_el = pt.find("ns:position", ns)
                qty_el = pt.find("ns:quantity", ns)
                if pos_el is None or pos_el.text is None or qty_el is None or qty_el.text is None:
                    continue
                dt = start + timedelta(minutes=(int(pos_el.text) - 1) * step)
                hour = dt.replace(minute=0, second=0, microsecond=0)
                buckets[hour].append(float(qty_el.text))
            for hour, vals in buckets.items():
                totals[hour] += sum(vals) / len(vals)
    return dict(totals)


class ENTSOEForecastSource:
    def __init__(self, security_token: str) -> None:
        self._token = security_token
        self._client = shared_client(timeout=20.0)

    def can_forecast(self, grid_zone: str) -> bool:
        return bool(self._token) and grid_zone in ENTSOE_ZONE_MAP

    async def _fetch(self, params: dict) -> str:
        resp = await get_with_retry(
            self._client,
            API_URL,
            params={"securityToken": self._token, **params},
            semaphore=ENTSOE_SEMAPHORE,
        )
        resp.raise_for_status()
        return resp.text

    async def _zone_series(self, grid_zone: str) -> dict[datetime, float]:
        """Forecasted VRE share of load per absolute UTC hour, cached per zone."""
        cached = _SERIES_CACHE.get(grid_zone)
        if cached and time.monotonic() - cached[0] < _SERIES_TTL_SECONDS:
            return cached[1]

        eic = ENTSOE_ZONE_MAP.get(grid_zone)
        if not eic or not self._token:
            return {}

        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        period_start = now.strftime("%Y%m%d%H00")
        period_end = (now + timedelta(hours=48)).strftime("%Y%m%d%H00")

        try:
            gen_xml = await self._fetch(
                {
                    "documentType": "A69",  # generation forecast (wind/solar)
                    "processType": "A01",  # day ahead
                    "in_Domain": eic,
                    "periodStart": period_start,
                    "periodEnd": period_end,
                }
            )
            load_xml = await self._fetch(
                {
                    "documentType": "A65",  # total load forecast
                    "processType": "A01",
                    "outBiddingZone_Domain": eic,
                    "periodStart": period_start,
                    "periodEnd": period_end,
                }
            )
        except Exception:
            return {}

        vre = _series_by_hour(gen_xml, _VRE_PSR)
        load = _series_by_hour(load_xml, None)
        series = {
            hour: min(1.0, max(0.0, vre[hour] / mw_load))
            for hour, mw_load in load.items()
            if mw_load > 0 and hour in vre
        }
        if series:
            _SERIES_CACHE[grid_zone] = (time.monotonic(), series)
        return series

    async def vre_fraction_curve(self, grid_zone: str, max_hours: int) -> dict[int, float]:
        """Forecasted variable-renewable share of load per hour offset from now.

        Returns {hour_offset: vre_fraction in 0..1}. Empty if the zone isn't an
        ENTSO-E zone, the token is missing, or the forecast is unavailable.
        """
        series = await self._zone_series(grid_zone)
        if not series:
            return {}
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        curve: dict[int, float] = {}
        for offset in range(0, max_hours + 1):
            frac = series.get(now + timedelta(hours=offset))
            if frac is not None:
                curve[offset] = frac
        return curve
