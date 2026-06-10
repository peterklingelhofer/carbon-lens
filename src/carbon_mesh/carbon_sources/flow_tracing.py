"""Consumption-based carbon intensity via electricity flow tracing.

Production-based intensity only counts what a zone *generates*. But grids import
and export power, so what a region actually *consumes* can be much cleaner or
dirtier than what it produces. Flow tracing (Tranberg et al., 2019) attributes
emissions across the interconnected network: the intensity of everything leaving
a zone equals the intensity of its whole consumed mix, so for every zone i

    c_i * (P_i + imports_i) = P_i * I_i + Σ_j  F_ji * c_j

where P_i is local generation, I_i its production intensity, and F_ji the power
flowing from j into i. That's a linear system A·c = b. The matrix is diagonally
dominant (the diagonal P_i + imports_i is >= the off-diagonal import sum), so
Gauss-Seidel iteration converges -- no numpy needed.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from carbon_mesh.carbon_sources.entsoe import ENTSOE_ZONE_MAP, ENTSOECarbonSource
from carbon_mesh.carbon_sources.http_pool import ENTSOE_SEMAPHORE, get_with_retry, shared_client
from carbon_mesh.carbon_sources.xml_safe import parse_xml

A11_URL = "https://web-api.tp.entsoe.eu/api"

# A connected slice of the European grid covering our cloud-region zones plus the
# key neighbours they trade with, so imports are attributed to a real source
# rather than ignored. Bigger sets mean more ENTSO-E calls; this is a pragmatic
# cut of the well-interconnected continental + GB/IE network.
TRACED_ZONES = [
    "FR",
    "DE",
    "NL",
    "BE",
    "CH",
    "AT",
    "ES",
    "PT",
    "IT-NO",
    "PL",
    "CZ",
    "GB",
    "IE",
    "DK-DK1",
]

# Undirected interconnector borders among TRACED_ZONES.
BORDERS = [
    ("FR", "DE"),
    ("FR", "BE"),
    ("FR", "CH"),
    ("FR", "ES"),
    ("FR", "IT-NO"),
    ("FR", "GB"),
    ("DE", "NL"),
    ("DE", "CH"),
    ("DE", "AT"),
    ("DE", "PL"),
    ("DE", "CZ"),
    ("DE", "DK-DK1"),
    ("NL", "BE"),
    ("NL", "GB"),
    ("CH", "AT"),
    ("CH", "IT-NO"),
    ("AT", "CZ"),
    ("AT", "IT-NO"),
    ("ES", "PT"),
    ("PL", "CZ"),
    ("GB", "IE"),
]


def trace_consumption_intensity(
    production_mw: dict[str, float],
    production_intensity: dict[str, float],
    flows_mw: dict[tuple[str, str], float],
    *,
    max_iter: int = 200,
    tol: float = 1e-4,
) -> dict[str, float]:
    """Solve for consumption-based intensity per zone.

    Args:
        production_mw: zone -> local generation (MW).
        production_intensity: zone -> production carbon intensity (gCO2/kWh).
        flows_mw: (from_zone, to_zone) -> power flowing from->to (MW, >= 0).
        max_iter / tol: Gauss-Seidel stopping conditions.

    Returns: zone -> consumption-based intensity (gCO2/kWh). Only zones present
    in production_mw are returned; flows to/from unknown zones are ignored.
    """
    zones = list(production_mw)
    if not zones:
        return {}

    # imports_into[i] = list of (j, F_ji); inflow[i] = P_i + Σ F_ji.
    imports_into: dict[str, list[tuple[str, float]]] = {z: [] for z in zones}
    for (src, dst), mw in flows_mw.items():
        if mw <= 0 or src not in production_mw or dst not in production_mw:
            continue
        imports_into[dst].append((src, mw))

    inflow = {z: production_mw[z] + sum(mw for _, mw in imports_into[z]) for z in zones}

    # Initialise consumption intensity at production intensity, then relax.
    c = {z: production_intensity.get(z, 0.0) for z in zones}
    for _ in range(max_iter):
        delta = 0.0
        for z in zones:
            denom = inflow[z]
            if denom <= 0:
                continue
            imported = sum(mw * c[src] for src, mw in imports_into[z])
            new_c = (production_mw[z] * production_intensity.get(z, 0.0) + imported) / denom
            delta = max(delta, abs(new_c - c[z]))
            c[z] = new_c
        if delta < tol:
            break

    return {z: round(c[z], 1) for z in zones}


def _parse_flow_latest(xml_text: str) -> float | None:
    """Most recent physical-flow value (MW) from an ENTSO-E A11 document."""
    try:
        root = parse_xml(xml_text)
    except Exception:
        return None
    ns = {"ns": root.tag.split("}")[0].strip("{")}
    latest: float | None = None
    for ts in root.findall(".//ns:TimeSeries", ns):
        for pt in ts.findall(".//ns:Point", ns):
            q = pt.find("ns:quantity", ns)
            if q is not None and q.text:
                latest = float(q.text)  # points are in time order; keep the last
    return latest


class ConsumptionIntensitySource:
    """Computes consumption-based intensity for the traced European network via
    ENTSO-E production (A75) + cross-border physical flows (A11). EU-only; needs
    the free ENTSO-E token."""

    def __init__(self, security_token: str) -> None:
        self._token = security_token
        self._client = shared_client(timeout=20.0)
        self._entsoe = ENTSOECarbonSource(security_token)

    async def _flow(self, in_eic: str, out_eic: str, period_start: str, period_end: str) -> float:
        """Latest physical flow out_eic -> in_eic (MW); 0 on any failure."""
        try:
            resp = await get_with_retry(
                self._client,
                A11_URL,
                params={
                    "securityToken": self._token,
                    "documentType": "A11",
                    "in_Domain": in_eic,
                    "out_Domain": out_eic,
                    "periodStart": period_start,
                    "periodEnd": period_end,
                },
                semaphore=ENTSOE_SEMAPHORE,
            )
            resp.raise_for_status()
            return _parse_flow_latest(resp.text) or 0.0
        except Exception:
            return 0.0

    async def compute(self) -> dict[str, float]:
        """Return zone -> consumption-based intensity (gCO2/kWh) for traced zones."""
        if not self._token:
            return {}

        prod = await self._entsoe.get_carbon_intensity_batch(TRACED_ZONES)
        production_mw = {z: ci.grid_load_mw for z, ci in prod.items() if ci.grid_load_mw}
        production_intensity = {z: ci.carbon_intensity_gco2_kwh for z, ci in prod.items()}
        if not production_mw:
            return {}

        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        period_start = (now - timedelta(hours=2)).strftime("%Y%m%d%H00")
        period_end = now.strftime("%Y%m%d%H00")

        pairs = [(a, b) for a, b in BORDERS if a in production_mw and b in production_mw]
        tasks = []
        for a, b in pairs:
            ea, eb = ENTSOE_ZONE_MAP[a], ENTSOE_ZONE_MAP[b]
            tasks.append(self._flow(ea, eb, period_start, period_end))  # b -> a
            tasks.append(self._flow(eb, ea, period_start, period_end))  # a -> b
        settled = await asyncio.gather(*tasks)

        flows: dict[tuple[str, str], float] = {}
        for i, (a, b) in enumerate(pairs):
            net = (settled[2 * i] or 0.0) - (settled[2 * i + 1] or 0.0)  # net b -> a
            if net > 0:
                flows[(b, a)] = net
            elif net < 0:
                flows[(a, b)] = -net

        return trace_consumption_intensity(
            {z: float(v) for z, v in production_mw.items()}, production_intensity, flows
        )
