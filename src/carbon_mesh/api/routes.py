from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
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
    provider: str | None = None,
    mapper: GridMapper = Depends(get_grid_mapper),
):
    """List all supported cloud regions."""
    regions = mapper.list_regions(provider)
    response = JSONResponse(content=[r.model_dump() for r in regions])
    # Region list is static — cache aggressively
    response.headers["Cache-Control"] = "public, max-age=3600"
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
