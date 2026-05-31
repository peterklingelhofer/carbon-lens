from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from carbon_mesh.db.models import EmissionsRecordDB
from carbon_mesh.models.accounting import CarbonSavingsReport, EmissionsRecord
from carbon_mesh.models.routing import RouteResponse


class CarbonTracker:
    """In-memory tracker — used when no DB is available (tests, dev mode)."""

    def __init__(self) -> None:
        self._records: list[EmissionsRecord] = []

    def record(self, response: RouteResponse) -> EmissionsRecord:
        chosen = response.recommended
        worst_intensity = chosen.carbon_intensity_gco2_kwh
        if response.alternatives:
            worst_intensity = max(a.carbon_intensity_gco2_kwh for a in response.alternatives)
            worst_intensity = max(worst_intensity, chosen.carbon_intensity_gco2_kwh)

        saved = worst_intensity - chosen.carbon_intensity_gco2_kwh

        rec = EmissionsRecord(
            request_id=response.request_id,
            timestamp=datetime.now(timezone.utc),
            chosen_provider=chosen.provider,
            chosen_region=chosen.region,
            chosen_grid_zone=chosen.grid_zone,
            chosen_carbon_intensity=chosen.carbon_intensity_gco2_kwh,
            worst_carbon_intensity=worst_intensity,
            carbon_saved_gco2_kwh=saved,
        )
        self._records.append(rec)
        return rec

    def report(self) -> CarbonSavingsReport:
        total_saved = sum(r.carbon_saved_gco2_kwh for r in self._records)
        avg_renewable = 0.0
        return CarbonSavingsReport(
            total_requests=len(self._records),
            total_carbon_saved_gco2_kwh=round(total_saved, 2),
            avg_renewable_percentage=avg_renewable,
            records=list(self._records),
        )


class DBCarbonTracker:
    """Postgres-backed tracker for production."""

    async def record(
        self, session: AsyncSession, response: RouteResponse, api_key_id: str | None = None
    ) -> EmissionsRecordDB:
        chosen = response.recommended
        worst_intensity = chosen.carbon_intensity_gco2_kwh
        if response.alternatives:
            worst_intensity = max(a.carbon_intensity_gco2_kwh for a in response.alternatives)
            worst_intensity = max(worst_intensity, chosen.carbon_intensity_gco2_kwh)

        saved = worst_intensity - chosen.carbon_intensity_gco2_kwh

        db_record = EmissionsRecordDB(
            request_id=response.request_id,
            api_key_id=api_key_id,
            chosen_provider=chosen.provider,
            chosen_region=chosen.region,
            chosen_grid_zone=chosen.grid_zone,
            chosen_carbon_intensity=chosen.carbon_intensity_gco2_kwh,
            worst_carbon_intensity=worst_intensity,
            carbon_saved_gco2_kwh=saved,
            chosen_renewable_pct=chosen.renewable_percentage,
        )
        session.add(db_record)
        await session.commit()
        return db_record

    async def report(
        self, session: AsyncSession, api_key_id: str | None = None
    ) -> CarbonSavingsReport:
        query = select(EmissionsRecordDB)
        if api_key_id:
            query = query.where(EmissionsRecordDB.api_key_id == api_key_id)
        query = query.order_by(EmissionsRecordDB.timestamp.desc()).limit(1000)

        result = await session.execute(query)
        db_records = result.scalars().all()

        records = [
            EmissionsRecord(
                request_id=r.request_id,
                timestamp=r.timestamp,
                chosen_provider=r.chosen_provider,
                chosen_region=r.chosen_region,
                chosen_grid_zone=r.chosen_grid_zone,
                chosen_carbon_intensity=r.chosen_carbon_intensity,
                worst_carbon_intensity=r.worst_carbon_intensity,
                carbon_saved_gco2_kwh=r.carbon_saved_gco2_kwh,
            )
            for r in db_records
        ]

        total_saved = sum(r.carbon_saved_gco2_kwh for r in records)
        avg_renewable = 0.0
        if db_records:
            avg_renewable = round(
                sum(r.chosen_renewable_pct for r in db_records) / len(db_records), 1
            )

        return CarbonSavingsReport(
            total_requests=len(records),
            total_carbon_saved_gco2_kwh=round(total_saved, 2),
            avg_renewable_percentage=avg_renewable,
            records=records,
        )
