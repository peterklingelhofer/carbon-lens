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

# Cap on how many recent records a report aggregates, to bound query/memory cost
_REPORT_RECORD_LIMIT = 1000


def _baseline_intensity(response: RouteResponse) -> float:
    """Mean carbon intensity across all candidates (chosen + alternatives)."""
    candidates = [response.recommended.carbon_intensity_gco2_kwh]
    candidates += [a.carbon_intensity_gco2_kwh for a in response.alternatives]
    return sum(candidates) / len(candidates)


def _reduction(response: RouteResponse) -> tuple[float, float]:
    """Baseline intensity and the reduction the carbon-aware pick achieves vs it."""
    baseline = _baseline_intensity(response)
    reduction = baseline - response.recommended.carbon_intensity_gco2_kwh
    return baseline, reduction


def _summarize(records: list[EmissionsRecord]) -> tuple[float, float]:
    """Average intensity reduction and average renewable share across records."""
    n = len(records)
    if not n:
        return 0.0, 0.0
    avg_reduction = round(sum(r.intensity_reduction_gco2_kwh for r in records) / n, 2)
    avg_renewable = round(sum(r.chosen_renewable_pct for r in records) / n, 1)
    return avg_reduction, avg_renewable


class CarbonTracker:
    """In-memory tracker — used when no DB is available (tests, dev mode)."""

    def __init__(self) -> None:
        self._records: list[EmissionsRecord] = []

    def record(self, response: RouteResponse) -> EmissionsRecord:
        chosen = response.recommended
        baseline, reduction = _reduction(response)

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
        avg_reduction, avg_renewable = _summarize(self._records)
        return CarbonSavingsReport(
            total_requests=len(self._records),
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
        baseline, reduction = _reduction(response)

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
        query = query.order_by(EmissionsRecordDB.timestamp.desc()).limit(_REPORT_RECORD_LIMIT)

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

        avg_reduction, avg_renewable = _summarize(records)

        return CarbonSavingsReport(
            total_requests=len(records),
            avg_intensity_reduction_gco2_kwh=avg_reduction,
            baseline=_BASELINE,
            avg_renewable_percentage=avg_renewable,
            records=records,
        )
