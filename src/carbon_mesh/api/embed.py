"""Embeddable live carbon-intensity widget (HTML, for iframes).

A small self-contained card a blog or dashboard can drop in with one `<iframe>`:
shows a region's current intensity, colour-coded, with a "good time to run?" read.
Rendered server-side from the cached/snapshot source (no client fetch, no CORS).
Framing is allowed for these paths only (see the security-headers middleware).
"""

from __future__ import annotations

import html

from fastapi import APIRouter, Depends, Response

from carbon_mesh.api.deps import get_carbon_source, get_grid_mapper
from carbon_mesh.carbon_sources.base import CarbonDataSource
from carbon_mesh.colors import GRAY, intensity_color
from carbon_mesh.grid.mapper import GridMapper

embed_router = APIRouter(tags=["Embed"])

_CACHE_CONTROL = "public, max-age=600"
_SITE = "https://carbonlens.peterklingelhofer.workers.dev"


def _state(value: float) -> str:
    if value <= 150:
        return "Good time to run"
    if value <= 400:
        return "Moderate"
    return "High — consider waiting"


def render_embed(label: str, intensity: float, renewable: float, *, unknown: bool = False) -> str:
    safe = html.escape(label)
    if unknown:
        color = GRAY
        big = "—"
        meta = f"{safe} · region not found"
        state = "Unknown region"
    else:
        color = intensity_color(intensity)
        big = f'{round(intensity)}<span class="u"> gCO₂/kWh</span>'
        meta = f"{safe} · {round(renewable)}% renewable"
        state = _state(intensity)
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>Carbon Lens — {safe}</title><style>"
        ":root{color-scheme:dark light}*{box-sizing:border-box}"
        "body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;background:transparent}"
        "a.card{display:block;text-decoration:none;background:#0b1220;color:#e5e7eb;"
        "border:1px solid #1f2937;border-radius:12px;padding:14px 16px;max-width:320px}"
        ".hd{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:#9ca3af}"
        ".big{font-size:30px;font-weight:700;line-height:1.1;margin:2px 0}"
        ".u{font-size:12px;font-weight:400;color:#9ca3af}"
        ".meta{font-size:12px;color:#cbd5e1}.state{margin-top:8px;font-size:12px;font-weight:600}"
        ".ft{margin-top:10px;font-size:10px;color:#6b7280}"
        "</style></head><body>"
        f'<a class="card" href="{_SITE}/globe" target="_blank" rel="noopener">'
        '<div class="hd">carbon intensity</div>'
        f'<div class="big" style="color:{color}">{big}</div>'
        f'<div class="meta">{meta}</div>'
        f'<div class="state" style="color:{color}">{state}</div>'
        '<div class="ft">⚡ Carbon Lens — live grid carbon</div>'
        "</a></body></html>"
    )


def _html(markup: str) -> Response:
    return Response(
        content=markup,
        media_type="text/html; charset=utf-8",
        headers={"Cache-Control": _CACHE_CONTROL},
    )


# Zone-first route (declared before the same-arity region route so "zone" isn't
# matched as a provider)
@embed_router.get("/embed/zone/{grid_zone}", include_in_schema=False)
async def zone_embed(
    grid_zone: str,
    mapper: GridMapper = Depends(get_grid_mapper),
    source: CarbonDataSource = Depends(get_carbon_source),
) -> Response:
    known = {r.grid_zone for r in mapper.grid_zones()}
    if grid_zone not in known:
        return _html(render_embed(grid_zone, 0, 0, unknown=True))
    ci = await source.get_carbon_intensity(grid_zone)
    return _html(render_embed(grid_zone, ci.carbon_intensity_gco2_kwh, ci.renewable_percentage))


@embed_router.get("/embed/{provider}/{region}", include_in_schema=False)
async def region_embed(
    provider: str,
    region: str,
    mapper: GridMapper = Depends(get_grid_mapper),
    source: CarbonDataSource = Depends(get_carbon_source),
) -> Response:
    zone = mapper.get_grid_zone(provider, region)
    if zone is None:
        return _html(render_embed(f"{provider}/{region}", 0, 0, unknown=True))
    ci = await source.get_carbon_intensity(zone)
    return _html(
        render_embed(f"{provider}/{region}", ci.carbon_intensity_gco2_kwh, ci.renewable_percentage)
    )
