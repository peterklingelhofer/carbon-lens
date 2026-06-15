"""Live carbon-intensity status badges (SVG), for embedding in READMEs.

Shields-style two-segment SVG: a "carbon" label and the region's current intensity,
coloured green->red. Backed by the cached/snapshot source so rendering a badge never
hits upstream quotas. Note: GitHub serves README images through its camo proxy,
which caches aggressively -- so "live" means within camo's cache window.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from carbon_mesh.api.deps import get_carbon_source, get_grid_mapper
from carbon_mesh.carbon_sources.base import CarbonDataSource
from carbon_mesh.grid.mapper import GridMapper

badge_router = APIRouter(tags=["Badge"])

_CACHE_CONTROL = "public, max-age=600, s-maxage=600"
_GRAY = "#9ca3af"


def _color(value: float) -> str:
    if value <= 50:
        return "#22c55e"  # green
    if value <= 150:
        return "#84cc16"  # lime
    if value <= 300:
        return "#eab308"  # amber
    if value <= 500:
        return "#f97316"  # orange
    return "#ef4444"  # red


def _seg_width(text: str) -> int:
    # Verdana ~6.5px/char at 11px, plus 10px padding. Good enough for layout.
    return round(len(text) * 6.5) + 10


def render_badge(label: str, value: str, color: str) -> str:
    """A flat shields-style SVG badge. Inputs are app-controlled (fixed label, an
    integer value, fixed color), so no untrusted text reaches the markup."""
    lw = _seg_width(label)
    vw = _seg_width(value)
    total = lw + vw
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total}" height="20" '
        f'role="img" aria-label="{label}: {value}">'
        f"<title>{label}: {value}</title>"
        f'<clipPath id="r"><rect width="{total}" height="20" rx="3" fill="#fff"/></clipPath>'
        f'<g clip-path="url(#r)">'
        f'<rect width="{lw}" height="20" fill="#555"/>'
        f'<rect x="{lw}" width="{vw}" height="20" fill="{color}"/>'
        f'<rect width="{total}" height="20" fill="#000" fill-opacity="0.08"/>'
        f"</g>"
        f'<g fill="#fff" text-anchor="middle" '
        f'font-family="Verdana,Geneva,DejaVu Sans,sans-serif" font-size="11">'
        f'<text x="{lw / 2:.0f}" y="14">{label}</text>'
        f'<text x="{lw + vw / 2:.0f}" y="14">{value}</text>'
        f"</g></svg>"
    )


def _svg(svg: str) -> Response:
    return Response(
        content=svg, media_type="image/svg+xml", headers={"Cache-Control": _CACHE_CONTROL}
    )


async def _intensity_badge(zone: str, source: CarbonDataSource) -> Response:
    ci = await source.get_carbon_intensity(zone)
    value = round(ci.carbon_intensity_gco2_kwh)
    return _svg(render_badge("carbon", f"{value} gCO₂/kWh", _color(value)))


# Zone badge first so "/badge/zone/DE.svg" isn't captured by the same-arity
# "/badge/{provider}/{region}.svg" route below (provider="zone").
@badge_router.get("/badge/zone/{grid_zone}.svg", include_in_schema=False)
async def zone_badge(
    grid_zone: str,
    mapper: GridMapper = Depends(get_grid_mapper),
    source: CarbonDataSource = Depends(get_carbon_source),
) -> Response:
    known = {r.grid_zone for r in mapper.grid_zones()}
    if grid_zone not in known:
        return _svg(render_badge("carbon", "unknown zone", _GRAY))
    return await _intensity_badge(grid_zone, source)


@badge_router.get("/badge/{provider}/{region}.svg", include_in_schema=False)
async def region_badge(
    provider: str,
    region: str,
    mapper: GridMapper = Depends(get_grid_mapper),
    source: CarbonDataSource = Depends(get_carbon_source),
) -> Response:
    zone = mapper.get_grid_zone(provider, region)
    if zone is None:
        return _svg(render_badge("carbon", "unknown region", _GRAY))
    return await _intensity_badge(zone, source)
