import hashlib
import json as _json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from carbon_mesh.accounting.tracker import CarbonTracker, DBCarbonTracker
from carbon_mesh.api.deps import (
    get_carbon_source,
    get_db_tracker,
    get_engine,
    get_grid_mapper,
    get_session,
    get_tracker,
)
from carbon_mesh.auth.dependencies import require_api_key
from carbon_mesh.billing.usage import check_usage_limit, increment_usage, is_over_limit
from carbon_mesh.carbon_sources.base import CarbonDataSource
from carbon_mesh.config import settings
from carbon_mesh.db.models import ApiKeyRecord
from carbon_mesh.engine.router import RoutingEngine
from carbon_mesh.grid.mapper import GridMapper
from carbon_mesh.models.accounting import CarbonSavingsReport
from carbon_mesh.models.carbon import CarbonIntensity
from carbon_mesh.models.region import CloudRegion
from carbon_mesh.models.routing import RouteRequest, RouteResponse

router = APIRouter()


@router.post("/route", response_model=RouteResponse, tags=["Routing"])
async def route_workload(
    request: RouteRequest,
    engine: RoutingEngine = Depends(get_engine),
    tracker: CarbonTracker = Depends(get_tracker),
    db_tracker: DBCarbonTracker = Depends(get_db_tracker),
    session: AsyncSession | None = Depends(get_session),
    key: ApiKeyRecord | None = Depends(require_api_key),
) -> RouteResponse:
    """Find the greenest cloud region for your workload."""
    # Enforce usage limits when DB + auth are active
    if settings.use_database and session is not None and key is not None:
        status = await check_usage_limit(session, key)
        if is_over_limit(status):
            raise HTTPException(
                status_code=429,
                detail=f"Daily usage limit exceeded ({status.daily_limit} requests/day on {key.tier} tier). Upgrade at /api/v1/billing/plans.",
            )

    try:
        response = await engine.route(request.constraints)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if settings.use_database and session is not None:
        api_key_id = key.id if key else None
        await db_tracker.record(session, response, api_key_id)
        # Increment usage counter after successful routing
        if key is not None:
            await increment_usage(session, key.id)
    else:
        tracker.record(response)

    return response


@router.get("/regions", response_model=list[CloudRegion], tags=["Regions"])
async def list_regions(
    request: Request,
    provider: str | None = None,
    mapper: GridMapper = Depends(get_grid_mapper),
):
    """List all supported cloud regions."""
    regions = mapper.list_regions(provider)
    content = [r.model_dump() for r in regions]

    # ETag — region list is static, skip resending if unchanged
    etag = '"' + hashlib.md5(_json.dumps(content, sort_keys=True).encode()).hexdigest() + '"'
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers={"ETag": etag})

    response = JSONResponse(content=content)
    response.headers["Cache-Control"] = "public, max-age=3600"
    response.headers["ETag"] = etag
    return response


@router.get("/carbon/{provider}/{region}", response_model=CarbonIntensity, tags=["Carbon Data"])
async def get_carbon_intensity(
    provider: str,
    region: str,
    mapper: GridMapper = Depends(get_grid_mapper),
    source: CarbonDataSource = Depends(get_carbon_source),
) -> CarbonIntensity:
    """Get current carbon intensity for a specific cloud region."""
    zone = mapper.get_grid_zone(provider, region)
    if zone is None:
        raise HTTPException(status_code=404, detail=f"Unknown region: {provider}/{region}")
    return await source.get_carbon_intensity(zone)


@router.post("/carbon/batch", response_model=dict[str, CarbonIntensity], tags=["Carbon Data"])
async def get_carbon_intensity_batch(
    regions: list[dict[str, str]],
    mapper: GridMapper = Depends(get_grid_mapper),
    source: CarbonDataSource = Depends(get_carbon_source),
) -> dict[str, CarbonIntensity]:
    """Get carbon intensity for multiple regions in a single request.

    Body: list of ``{"provider": "aws", "region": "us-east-1"}`` objects.
    Returns a map of ``"provider/region"`` to carbon intensity.
    """
    # Multiple regions can share one grid zone (e.g. aws/us-east-1 and aws/us-east-2
    # are both US-MIDA-PJM), so map each zone to ALL of its requested region keys.
    zone_to_keys: dict[str, list[str]] = {}
    for r in regions:
        zone = mapper.get_grid_zone(r["provider"], r["region"])
        if zone is not None:
            zone_to_keys.setdefault(zone, []).append(f"{r['provider']}/{r['region']}")

    if not zone_to_keys:
        raise HTTPException(status_code=400, detail="No valid regions provided")

    intensities = await source.get_carbon_intensity_batch(list(zone_to_keys.keys()))

    return {
        key: intensity
        for zone, intensity in intensities.items()
        if zone in zone_to_keys
        for key in zone_to_keys[zone]
    }


@router.get("/carbon/zones", tags=["Carbon Data"])
async def list_grid_zones(
    mapper: GridMapper = Depends(get_grid_mapper),
) -> list[dict[str, str | list[str]]]:
    """List all supported electricity grid zones and the cloud regions mapped to each.

    Returns an array of objects with ``grid_zone``, ``regions`` (list of
    ``provider/region`` strings), and ``location`` for the first mapped region.
    """
    all_regions = mapper.list_regions()
    zone_map: dict[str, dict] = {}
    for r in all_regions:
        if r.grid_zone not in zone_map:
            zone_map[r.grid_zone] = {
                "grid_zone": r.grid_zone,
                "location": r.location,
                "regions": [],
            }
        zone_map[r.grid_zone]["regions"].append(f"{r.provider}/{r.region}")

    return sorted(zone_map.values(), key=lambda z: z["grid_zone"])


@router.get("/status/sources", tags=["System"])
async def source_health(
    source: CarbonDataSource = Depends(get_carbon_source),
) -> dict:
    """Check health and latency of each configured carbon data source.

    Queries a representative zone for each source and measures response time.
    """
    import asyncio
    import time

    from carbon_mesh.config import settings

    # Test zones — one per major source
    test_zones = {
        "UK Carbon Intensity": "GB",
        "EIA (US grid)": "US-MIDA-PJM",
        "AEMO (Australia)": "AU-NSW",
        "Grid India": "IN-NO",
        "ONS Brazil": "BR-SE",
        "Eskom (South Africa)": "ZA",
        "Open-Meteo (weather)": "DE",
    }

    if settings.eia_api_key:
        test_zones["EIA (US grid)"] = "US-MIDA-PJM"
    if settings.grid_status_api_key:
        test_zones["GridStatus (US ISOs)"] = "US-CAL-CISO"
    if settings.entsoe_token:
        test_zones["ENTSO-E (Europe)"] = "DE"

    results: dict[str, dict] = {}

    async def _check_source(name: str, zone: str) -> None:
        start = time.perf_counter()
        try:
            intensity = await source.get_carbon_intensity(zone)
            latency_ms = (time.perf_counter() - start) * 1000
            results[name] = {
                "status": "ok",
                "latency_ms": round(latency_ms, 1),
                "test_zone": zone,
                "carbon_intensity_gco2_kwh": intensity.carbon_intensity_gco2_kwh,
                "source": intensity.source,
            }
        except Exception as e:
            latency_ms = (time.perf_counter() - start) * 1000
            results[name] = {
                "status": "error",
                "latency_ms": round(latency_ms, 1),
                "test_zone": zone,
                "error": str(e),
            }

    await asyncio.gather(*[_check_source(name, zone) for name, zone in test_zones.items()])

    healthy = sum(1 for r in results.values() if r["status"] == "ok")
    return {
        "sources": results,
        "healthy": healthy,
        "total": len(results),
    }


@router.get("/accounting/savings", response_model=CarbonSavingsReport, tags=["Accounting"])
async def get_savings(
    tracker: CarbonTracker = Depends(get_tracker),
    db_tracker: DBCarbonTracker = Depends(get_db_tracker),
    session: AsyncSession | None = Depends(get_session),
    key: ApiKeyRecord | None = Depends(require_api_key),
) -> CarbonSavingsReport:
    """Get carbon savings report for all routed workloads."""
    if settings.use_database and session is not None:
        api_key_id = key.id if key else None
        return await db_tracker.report(session, api_key_id)
    return tracker.report()
