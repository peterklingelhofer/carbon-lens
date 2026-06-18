"""Postgres-backed org impact ledger (the optional system-of-record).

Hosts POST one row per carbon-aware run; org-statement reads recent rows back as the
same entry dicts the local ledger uses, so the same aggregation serves both.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from carbon_mesh.db.models import ImpactRecordDB


async def record_impact(
    session: AsyncSession, entry: dict, api_key_id: str | None = None
) -> ImpactRecordDB:
    rec = ImpactRecordDB(
        api_key_id=api_key_id,
        region=entry["region"],
        deferred_hours=int(entry.get("deferred_hours", 0) or 0),
        reduction_gco2_kwh=float(entry.get("reduction_gco2_kwh", 0.0) or 0.0),
        energy_kwh=entry.get("energy_kwh"),
        basis=entry.get("basis", "forecast"),
    )
    session.add(rec)
    await session.commit()
    return rec


async def recent_impacts(session: AsyncSession, since: datetime) -> list[dict]:
    """Recent impact rows as ledger-style entry dicts (for fleet_summary/org_statement)."""
    query = (
        select(ImpactRecordDB)
        .where(ImpactRecordDB.ts >= since)
        .order_by(ImpactRecordDB.ts.desc())
        .limit(10000)
    )
    rows = (await session.execute(query)).scalars().all()
    return [
        {
            "ts": r.ts.isoformat(),
            "region": r.region,
            "deferred_hours": r.deferred_hours,
            "reduction_gco2_kwh": r.reduction_gco2_kwh,
            "energy_kwh": r.energy_kwh,
            "basis": r.basis,
        }
        for r in rows
    ]
