"""Storage for Green SLAs, checks, and reports.

Two interchangeable backends behind one protocol: an in-memory store (the keyless
demo and tests) and a Postgres store (durable across restarts). The API picks one
per request via ``get_sla_repository``; everything else is backend-agnostic.
"""

from __future__ import annotations

from typing import Protocol, TypeVar

from pydantic import BaseModel
from sqlalchemy import Select, delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from carbon_mesh.db.models import GreenSLADB, SLACheckDB, SLAReportDB
from carbon_mesh.models.sla import GreenSLA, SLACheck, SLAReport

_M = TypeVar("_M", bound=BaseModel)

# Cap per-SLA check history so an in-memory instance can't grow unbounded.
_MAX_CHECKS = 10_000


class SLARepository(Protocol):
    async def create_sla(self, sla: GreenSLA) -> None: ...
    async def get_sla(self, sla_id: str) -> GreenSLA | None: ...
    async def list_slas(self, org_id: str) -> list[GreenSLA]: ...
    async def list_active_slas(self, org_id: str | None = None) -> list[GreenSLA]: ...
    async def update_sla(self, sla: GreenSLA) -> None: ...
    async def delete_sla(self, sla_id: str) -> bool: ...
    async def add_check(self, check: SLACheck) -> None: ...
    async def list_checks(self, sla_id: str, limit: int | None = None) -> list[SLACheck]: ...
    async def latest_check(self, sla_id: str) -> SLACheck | None: ...
    async def add_report(self, report: SLAReport) -> None: ...
    async def list_reports(self, sla_id: str) -> list[SLAReport]: ...


class InMemorySLARepository:
    """Process-local store. State is lost on restart -- the demo/test backend."""

    def __init__(self) -> None:
        self._slas: dict[str, GreenSLA] = {}
        self._checks: dict[str, list[SLACheck]] = {}
        self._reports: dict[str, list[SLAReport]] = {}

    async def create_sla(self, sla: GreenSLA) -> None:
        self._slas[sla.id] = sla
        self._checks.setdefault(sla.id, [])

    async def get_sla(self, sla_id: str) -> GreenSLA | None:
        return self._slas.get(sla_id)

    async def list_slas(self, org_id: str) -> list[GreenSLA]:
        return [s for s in self._slas.values() if s.org_id == org_id]

    async def list_active_slas(self, org_id: str | None = None) -> list[GreenSLA]:
        return [
            s for s in self._slas.values() if s.active and (org_id is None or s.org_id == org_id)
        ]

    async def update_sla(self, sla: GreenSLA) -> None:
        self._slas[sla.id] = sla

    async def delete_sla(self, sla_id: str) -> bool:
        existed = sla_id in self._slas
        self._slas.pop(sla_id, None)
        self._checks.pop(sla_id, None)
        self._reports.pop(sla_id, None)
        return existed

    async def add_check(self, check: SLACheck) -> None:
        checks = self._checks.setdefault(check.sla_id, [])
        checks.append(check)
        if len(checks) > _MAX_CHECKS:
            self._checks[check.sla_id] = checks[-(_MAX_CHECKS // 2) :]

    async def list_checks(self, sla_id: str, limit: int | None = None) -> list[SLACheck]:
        checks = self._checks.get(sla_id, [])
        return checks[-limit:] if limit else list(checks)

    async def latest_check(self, sla_id: str) -> SLACheck | None:
        checks = self._checks.get(sla_id, [])
        return checks[-1] if checks else None

    async def add_report(self, report: SLAReport) -> None:
        self._reports.setdefault(report.sla_id, []).append(report)

    async def list_reports(self, sla_id: str) -> list[SLAReport]:
        return list(self._reports.get(sla_id, []))


class DBSLARepository:
    """Postgres-backed store. Each domain model round-trips through a JSON payload
    column, with a few indexed columns for filtering and ordering."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def _load_all(self, stmt: Select, model_cls: type[_M]) -> list[_M]:
        """Run a select and validate each row's JSON payload into the model."""
        rows = (await self._session.execute(stmt)).scalars().all()
        return [model_cls.model_validate_json(r.payload) for r in rows]

    async def create_sla(self, sla: GreenSLA) -> None:
        self._session.add(
            GreenSLADB(
                id=sla.id,
                org_id=sla.org_id,
                active=sla.active,
                updated_at=sla.updated_at,
                payload=sla.model_dump_json(),
            )
        )
        await self._session.commit()

    async def get_sla(self, sla_id: str) -> GreenSLA | None:
        row = await self._session.get(GreenSLADB, sla_id)
        return GreenSLA.model_validate_json(row.payload) if row else None

    async def list_slas(self, org_id: str) -> list[GreenSLA]:
        return await self._load_all(select(GreenSLADB).where(GreenSLADB.org_id == org_id), GreenSLA)

    async def list_active_slas(self, org_id: str | None = None) -> list[GreenSLA]:
        stmt = select(GreenSLADB).where(GreenSLADB.active.is_(True))
        if org_id is not None:
            stmt = stmt.where(GreenSLADB.org_id == org_id)
        return await self._load_all(stmt, GreenSLA)

    async def update_sla(self, sla: GreenSLA) -> None:
        row = await self._session.get(GreenSLADB, sla.id)
        if row is None:
            return
        row.payload = sla.model_dump_json()
        row.active = sla.active
        row.updated_at = sla.updated_at
        await self._session.commit()

    async def delete_sla(self, sla_id: str) -> bool:
        row = await self._session.get(GreenSLADB, sla_id)
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.execute(delete(SLACheckDB).where(SLACheckDB.sla_id == sla_id))
        await self._session.execute(delete(SLAReportDB).where(SLAReportDB.sla_id == sla_id))
        await self._session.commit()
        return True

    async def add_check(self, check: SLACheck) -> None:
        self._session.add(
            SLACheckDB(
                id=check.id,
                sla_id=check.sla_id,
                checked_at=check.checked_at,
                payload=check.model_dump_json(),
            )
        )
        await self._session.commit()

    async def list_checks(self, sla_id: str, limit: int | None = None) -> list[SLACheck]:
        stmt = select(SLACheckDB).where(SLACheckDB.sla_id == sla_id).order_by(SLACheckDB.checked_at)
        checks = await self._load_all(stmt, SLACheck)
        return checks[-limit:] if limit else checks

    async def latest_check(self, sla_id: str) -> SLACheck | None:
        stmt = (
            select(SLACheckDB)
            .where(SLACheckDB.sla_id == sla_id)
            .order_by(SLACheckDB.checked_at.desc())
            .limit(1)
        )
        row = (await self._session.execute(stmt)).scalars().first()
        return SLACheck.model_validate_json(row.payload) if row else None

    async def add_report(self, report: SLAReport) -> None:
        self._session.add(
            SLAReportDB(
                id=report.id,
                sla_id=report.sla_id,
                generated_at=report.generated_at,
                payload=report.model_dump_json(),
            )
        )
        await self._session.commit()

    async def list_reports(self, sla_id: str) -> list[SLAReport]:
        stmt = (
            select(SLAReportDB)
            .where(SLAReportDB.sla_id == sla_id)
            .order_by(SLAReportDB.generated_at)
        )
        return await self._load_all(stmt, SLAReport)
