from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from carbon_mesh.db.models import EmissionsRecordDB
from carbon_mesh.models.accounting import CarbonSavingsReport, EmissionsRecord
from carbon_mesh.models.routing import RouteResponse

# The counterfactual: what you'd emit picking among the SAME candidate regions
# without carbon-awareness. Mean of the candidates -- not the single worst, which
# would assume you'd otherwise deliberately choose the dirtiest option and so
# overstate the benefit.
_BASELINE = "mean carbon intensity of the candidate regions considered (a carbon-blind pick)"


def _baseline_intensity(response: RouteResponse) -> float:
    """Mean carbon intensity across all candidates (chosen + alternatives)."""
    candidates = [response.recommended.carbon_intensity_gco2_kwh]
    candidates += [a.carbon_intensity_gco2_kwh for a in response.alternatives]
    return sum(candidates) / len(candidates)


class CarbonTracker:
    """In-memory tracker — used when no DB is available (tests, dev mode)."""

    def __init__(self) -> None:
        self._records: list[EmissionsRecord] = []

    def record(self, response: RouteResponse) -> EmissionsRecord:
        chosen = response.recommended
        baseline = _baseline_intensity(response)
        reduction = baseline - chosen.carbon_intensity_gco2_kwh

        rec = EmissionsRecord(
            request_id=response.request_id,
            timestamp=datetime.now(timezone.utc),
            chosen_provider=chosen.provider,
            chosen_region=chosen.region,
            chosen_grid_zone=chosen.grid_zone,
            chosen_carbon_intensity=chosen.carbon_intensity_gco2_kwh,
            baseline_carbon_intensity=round(baseline, 2),
            intensity_reduction_gco2_kwh=round(reduction, 2),
            chosen_renewable_pct=chosen.renewable_percentage,
        )
        self._records.append(rec)
        return rec

    def report(self) -> CarbonSavingsReport:
        n = len(self._records)
        avg_reduction = (
            round(sum(r.intensity_reduction_gco2_kwh for r in self._records) / n, 2) if n else 0.0
        )
        avg_renewable = (
            round(sum(r.chosen_renewable_pct for r in self._records) / n, 1) if n else 0.0
        )
        return CarbonSavingsReport(
            total_requests=n,
            avg_intensity_reduction_gco2_kwh=avg_reduction,
            baseline=_BASELINE,
            avg_renewable_percentage=avg_renewable,
            records=list(self._records),
        )


class DBCarbonTracker:
    """Postgres-backed tracker for production."""

    async def record(
        self, session: AsyncSession, response: RouteResponse, api_key_id: str | None = None
    ) -> EmissionsRecordDB:
        chosen = response.recommended
        baseline = _baseline_intensity(response)
        reduction = baseline - chosen.carbon_intensity_gco2_kwh

        db_record = EmissionsRecordDB(
            request_id=response.request_id,
            api_key_id=api_key_id,
            chosen_provider=chosen.provider,
            chosen_region=chosen.region,
            chosen_grid_zone=chosen.grid_zone,
            chosen_carbon_intensity=chosen.carbon_intensity_gco2_kwh,
            baseline_carbon_intensity=round(baseline, 2),
            intensity_reduction_gco2_kwh=round(reduction, 2),
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
                baseline_carbon_intensity=r.baseline_carbon_intensity,
                intensity_reduction_gco2_kwh=r.intensity_reduction_gco2_kwh,
                chosen_renewable_pct=r.chosen_renewable_pct,
            )
            for r in db_records
        ]

        n = len(records)
        avg_reduction = (
            round(sum(r.intensity_reduction_gco2_kwh for r in records) / n, 2) if n else 0.0
        )
        avg_renewable = round(sum(r.chosen_renewable_pct for r in db_records) / n, 1) if n else 0.0

        return CarbonSavingsReport(
            total_requests=n,
            avg_intensity_reduction_gco2_kwh=avg_reduction,
            baseline=_BASELINE,
            avg_renewable_percentage=avg_renewable,
            records=records,
        )
