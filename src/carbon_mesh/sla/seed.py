"""Idempotent demo-SLA seeding.

The dashboard's SLA page is scoped to a shared ``demo`` org. Seeding one SLA at
startup means the page shows real, accumulating compliance data instead of an
empty state -- and because it runs on every startup (and Render free cold-starts
on each request after idling), the demo SLA self-heals: restored after a 30-day
DB reset, a redeploy, or a visitor deleting it. Then the cron / in-process monitor
fills its check history. Everything here is best-effort and never blocks startup.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from carbon_mesh.models.sla import GreenSLA, SLACheckFrequency
from carbon_mesh.sla.repository import SLARepository

logger = logging.getLogger(__name__)

DEMO_ORG_ID = "demo"
DEMO_SLA_ID = "demo-seed-sla"
# A small, fixed region set so the seed check is cheap (3 zones, not all regions).
DEMO_REGIONS = ["us-east-1", "us-west-2", "eu-west-3"]


def build_demo_sla() -> GreenSLA:
    now = datetime.now(timezone.utc)
    return GreenSLA(
        id=DEMO_SLA_ID,
        org_id=DEMO_ORG_ID,
        name="Demo Green SLA",
        max_carbon_intensity_gco2_kwh=200.0,
        min_renewable_percentage=40.0,
        providers=["aws"],
        regions=DEMO_REGIONS,
        check_frequency=SLACheckFrequency.HOURLY,
        created_at=now,
        updated_at=now,
        active=True,
    )


async def ensure_demo_sla(repo: SLARepository) -> bool:
    """Create the demo SLA if missing. Idempotent (a no-op when it already exists),
    so it's safe to run on every startup. Returns True if it created one."""
    if await repo.get_sla(DEMO_SLA_ID) is not None:
        return False
    await repo.create_sla(build_demo_sla())
    return True


async def _seed_initial_check(repo: SLARepository) -> None:
    """Run one compliance check so the SLA page has data before the cron's first run."""
    from carbon_mesh.api.deps import get_carbon_source, get_grid_mapper
    from carbon_mesh.sla.engine import SLAEngine

    sla = await repo.get_sla(DEMO_SLA_ID)
    if sla is None:
        return
    engine = SLAEngine(carbon_source=get_carbon_source(), grid_mapper=get_grid_mapper())
    check = await engine.check_sla(sla)
    await repo.add_check(check)


async def seed_demo_sla() -> None:
    """Ensure the demo SLA exists at startup, and run one initial check when it was
    just created. Best-effort: any failure is logged and swallowed so it can never
    block app startup."""
    from carbon_mesh.config import settings

    try:
        if settings.use_database:
            from carbon_mesh.db.engine import AsyncSessionLocal
            from carbon_mesh.sla.repository import DBSLARepository

            async with AsyncSessionLocal() as session:
                repo: SLARepository = DBSLARepository(session)
                created = await ensure_demo_sla(repo)
                if created:
                    await _seed_initial_check(repo)
        else:
            from carbon_mesh.api.deps import _in_memory_sla_repo

            created = await ensure_demo_sla(_in_memory_sla_repo)
            if created:
                await _seed_initial_check(_in_memory_sla_repo)
        if created:
            logger.info("Seeded demo SLA (%s) with an initial check.", DEMO_SLA_ID)
    except Exception as e:
        logger.warning("Demo SLA seed skipped: %s", e)
