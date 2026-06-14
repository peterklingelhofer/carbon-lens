"""Round-trip tests for the Postgres-backed SLA repository.

Runs against an in-memory SQLite (via aiosqlite) so the durable path is exercised
without a real Postgres -- the repo only uses portable SQLAlchemy, and each domain
model round-trips through a JSON payload column.
"""

from datetime import datetime, timedelta, timezone

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from carbon_mesh.db.models import Base
from carbon_mesh.models.sla import GreenSLA, SLACheck, SLAReport, SLAStatus
from carbon_mesh.sla.repository import DBSLARepository


@pytest_asyncio.fixture
async def repo():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    async with session_maker() as session:
        yield DBSLARepository(session)
    await engine.dispose()


def _sla(sla_id: str = "sla-1", org: str = "org-1", active: bool = True) -> GreenSLA:
    now = datetime(2026, 6, 14, tzinfo=timezone.utc)
    return GreenSLA(
        id=sla_id,
        org_id=org,
        name="Green target",
        max_carbon_intensity_gco2_kwh=300.0,
        min_renewable_percentage=40.0,
        created_at=now,
        updated_at=now,
        active=active,
    )


def _check(sla_id: str, when: datetime, status: SLAStatus = SLAStatus.COMPLIANT) -> SLACheck:
    return SLACheck(
        id=f"chk-{when.isoformat()}",
        sla_id=sla_id,
        checked_at=when,
        status=status,
        avg_carbon_intensity_gco2_kwh=100.0,
        max_carbon_intensity_gco2_kwh=120.0,
        min_carbon_intensity_gco2_kwh=80.0,
        avg_renewable_percentage=60.0,
        regions_checked=3,
        regions_compliant=3,
        regions_breached=0,
        breached_regions=[{"region": "x"}],  # nested data must survive the round-trip
        target_max_carbon=300.0,
        target_min_renewable=40.0,
    )


async def test_sla_crud_roundtrip(repo: DBSLARepository):
    await repo.create_sla(_sla())
    got = await repo.get_sla("sla-1")
    assert got is not None and got.name == "Green target"

    assert [s.id for s in await repo.list_slas("org-1")] == ["sla-1"]
    assert await repo.list_slas("other-org") == []

    # update flips active; list_active_slas should then exclude it
    await repo.update_sla(_sla(active=False))
    assert await repo.list_active_slas() == []

    assert await repo.delete_sla("sla-1") is True
    assert await repo.get_sla("sla-1") is None
    assert await repo.delete_sla("sla-1") is False  # idempotent


async def test_checks_ordered_and_latest(repo: DBSLARepository):
    await repo.create_sla(_sla())
    t0 = datetime(2026, 6, 14, 0, tzinfo=timezone.utc)
    await repo.add_check(_check("sla-1", t0))
    await repo.add_check(_check("sla-1", t0 + timedelta(hours=1), SLAStatus.BREACHED))

    checks = await repo.list_checks("sla-1")
    assert [c.status for c in checks] == [SLAStatus.COMPLIANT, SLAStatus.BREACHED]  # oldest first
    assert checks[-1].breached_regions == [{"region": "x"}]  # nested payload preserved

    latest = await repo.latest_check("sla-1")
    assert latest is not None and latest.status == SLAStatus.BREACHED


async def test_delete_cascades_checks_and_reports(repo: DBSLARepository):
    await repo.create_sla(_sla())
    await repo.add_check(_check("sla-1", datetime(2026, 6, 14, tzinfo=timezone.utc)))
    report = SLAReport(
        id="rep-1",
        sla_id="sla-1",
        org_id="org-1",
        org_name="Org",
        sla_name="Green target",
        period_start=datetime(2026, 6, 1, tzinfo=timezone.utc),
        period_end=datetime(2026, 6, 14, tzinfo=timezone.utc),
        generated_at=datetime(2026, 6, 14, tzinfo=timezone.utc),
        total_checks=1,
        compliant_checks=1,
        warning_checks=0,
        breached_checks=0,
        compliance_percentage=100.0,
        avg_carbon_intensity_gco2_kwh=100.0,
        max_carbon_intensity_gco2_kwh=120.0,
        avg_renewable_percentage=60.0,
        min_renewable_percentage=55.0,
        target_max_carbon=300.0,
        target_min_renewable=40.0,
    )
    await repo.add_report(report)
    assert len(await repo.list_reports("sla-1")) == 1

    await repo.delete_sla("sla-1")
    assert await repo.list_checks("sla-1") == []
    assert await repo.list_reports("sla-1") == []
