"""Carbon-aware scheduling API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from carbon_mesh.api.deps import get_carbon_source, get_grid_mapper
from carbon_mesh.auth.dependencies import require_api_key
from carbon_mesh.scheduler.engine import (
    CronSchedule,
    ScheduleRecommendation,
    ScheduleStrategy,
    SchedulingEngine,
)

router = APIRouter(
    prefix="/api/v1/scheduler",
    tags=["Scheduling"],
    dependencies=[Depends(require_api_key)],
)

# In-memory store for scheduled jobs
_schedule_store: dict[str, CronSchedule] = {}


def _get_engine() -> SchedulingEngine:
    from carbon_mesh.carbon_sources.entsoe_forecast import ENTSOEForecastSource
    from carbon_mesh.carbon_sources.snapshot_source import SnapshotBackedSource
    from carbon_mesh.config import settings

    # Read current intensity from the published snapshot (one cached fetch of all
    # zones) instead of live-fetching dozens per request. Skipped under "mock"
    # so the test suite stays offline.
    source = get_carbon_source()
    if settings.snapshot_url and settings.carbon_source != "mock":
        source = SnapshotBackedSource(settings.snapshot_url, source)

    return SchedulingEngine(
        carbon_source=source,
        grid_mapper=get_grid_mapper(),
        forecast_source=ENTSOEForecastSource(settings.entsoe_token),
    )


# --- Request models ---


class FindWindowRequest(BaseModel):
    job_duration_minutes: int = Field(ge=1, le=1440, default=30)
    providers: list[str] = Field(default_factory=lambda: ["aws", "gcp", "azure"])
    preferred_regions: list[str] = Field(default_factory=list)
    strategy: ScheduleStrategy = ScheduleStrategy.LOWEST_CARBON
    max_delay_hours: int = Field(ge=1, le=168, default=24)


class CreateScheduleRequest(BaseModel):
    name: str
    org_id: str
    job_duration_minutes: int = Field(ge=1, le=1440, default=30)
    providers: list[str] = Field(default_factory=lambda: ["aws", "gcp", "azure"])
    preferred_regions: list[str] = Field(default_factory=list)
    strategy: ScheduleStrategy = ScheduleStrategy.LOWEST_CARBON
    max_delay_hours: int = Field(ge=1, le=168, default=24)


# --- Endpoints ---


@router.post("/find-window", response_model=ScheduleRecommendation)
async def find_optimal_window(req: FindWindowRequest) -> ScheduleRecommendation:
    """Find the optimal low-carbon time window for a batch job.

    Evaluates carbon intensity across all regions and time slots within the
    specified window, and returns the greenest option.

    Use this to decide when to run CI/CD pipelines, batch processing,
    ML training, or any deferrable workload.
    """
    engine = _get_engine()
    return await engine.find_optimal_window(
        job_duration_minutes=req.job_duration_minutes,
        providers=req.providers,
        preferred_regions=req.preferred_regions,
        strategy=req.strategy,
        max_delay_hours=req.max_delay_hours,
    )


@router.get("/now", response_model=ScheduleRecommendation)
async def best_region_now(
    duration_minutes: int = Query(30, ge=1, le=1440),
    providers: str = Query("aws,gcp,azure"),
) -> ScheduleRecommendation:
    """Quick check: what's the greenest region to run a job RIGHT NOW?

    Simpler than /find-window — just tells you the best region at this moment.
    """
    engine = _get_engine()
    provider_list = [p.strip() for p in providers.split(",")]
    return await engine.find_optimal_window(
        job_duration_minutes=duration_minutes,
        providers=provider_list,
        max_delay_hours=1,  # Only check current hour
    )


@router.post("/schedules", response_model=CronSchedule)
async def create_schedule(req: CreateScheduleRequest) -> CronSchedule:
    """Create a recurring carbon-aware schedule.

    Define a job's requirements and the scheduler will recommend optimal
    execution windows each time it runs.
    """
    schedule = CronSchedule(
        id=str(uuid.uuid4()),
        name=req.name,
        org_id=req.org_id,
        job_duration_minutes=req.job_duration_minutes,
        providers=req.providers,
        preferred_regions=req.preferred_regions,
        strategy=req.strategy,
        max_delay_hours=req.max_delay_hours,
        created_at=datetime.now(timezone.utc),
    )
    _schedule_store[schedule.id] = schedule
    return schedule


@router.get("/schedules", response_model=list[CronSchedule])
async def list_schedules(org_id: str = Query(...)) -> list[CronSchedule]:
    """List all scheduled jobs for an organization."""
    return [s for s in _schedule_store.values() if s.org_id == org_id]


@router.get("/schedules/{schedule_id}", response_model=CronSchedule)
async def get_schedule(schedule_id: str) -> CronSchedule:
    """Get a specific schedule."""
    schedule = _schedule_store.get(schedule_id)
    if not schedule:
        raise HTTPException(404, f"Schedule {schedule_id} not found")
    return schedule


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(schedule_id: str) -> dict:
    """Delete a schedule."""
    if schedule_id not in _schedule_store:
        raise HTTPException(404, f"Schedule {schedule_id} not found")
    del _schedule_store[schedule_id]
    return {"deleted": schedule_id}


@router.post("/schedules/{schedule_id}/next", response_model=ScheduleRecommendation)
async def get_next_window(schedule_id: str) -> ScheduleRecommendation:
    """Get the next optimal execution window for a scheduled job.

    Uses the schedule's configuration to find the best upcoming time slot.
    """
    schedule = _schedule_store.get(schedule_id)
    if not schedule:
        raise HTTPException(404, f"Schedule {schedule_id} not found")

    engine = _get_engine()
    return await engine.find_optimal_window(
        job_duration_minutes=schedule.job_duration_minutes,
        providers=schedule.providers,
        preferred_regions=schedule.preferred_regions,
        strategy=schedule.strategy,
        max_delay_hours=schedule.max_delay_hours,
    )
