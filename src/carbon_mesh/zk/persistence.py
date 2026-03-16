"""Job state persistence — durable storage for ZK proof jobs.

Provides both in-memory (dev/test) and PostgreSQL (production) backends.
The orchestrator and executor use this to track job lifecycle state
across restarts and across the evaluate → prove → submit → claim pipeline.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from carbon_mesh.models.zk import (
    ComputeOption,
    DispatchDecision,
    JobResult,
    JobStatus,
    ProofJob,
)

logger = logging.getLogger(__name__)


@runtime_checkable
class JobStore(Protocol):
    """Protocol for durable job storage."""

    async def save_job(self, job: ProofJob) -> None: ...
    async def save_decision(self, decision: DispatchDecision) -> None: ...
    async def save_result(self, result: JobResult) -> None: ...
    async def update_status(self, job_id: str, status: JobStatus, error: str = "") -> None: ...
    async def get_job(self, job_id: str) -> ProofJob | None: ...
    async def get_decision(self, job_id: str) -> DispatchDecision | None: ...
    async def get_result(self, job_id: str) -> JobResult | None: ...
    async def list_jobs(self, status: JobStatus | None = None, limit: int = 100) -> list[ProofJob]: ...
    async def count_by_status(self) -> dict[str, int]: ...


class InMemoryJobStore:
    """In-memory job store for development and testing."""

    def __init__(self) -> None:
        self._jobs: dict[str, ProofJob] = {}
        self._decisions: dict[str, DispatchDecision] = {}
        self._results: dict[str, JobResult] = {}

    async def save_job(self, job: ProofJob) -> None:
        self._jobs[job.id] = job

    async def save_decision(self, decision: DispatchDecision) -> None:
        self._decisions[decision.job_id] = decision

    async def save_result(self, result: JobResult) -> None:
        self._results[result.job_id] = result

    async def update_status(self, job_id: str, status: JobStatus, error: str = "") -> None:
        if job_id in self._results:
            self._results[job_id] = self._results[job_id].model_copy(
                update={"status": status, "error": error}
            )

    async def get_job(self, job_id: str) -> ProofJob | None:
        return self._jobs.get(job_id)

    async def get_decision(self, job_id: str) -> DispatchDecision | None:
        return self._decisions.get(job_id)

    async def get_result(self, job_id: str) -> JobResult | None:
        return self._results.get(job_id)

    async def list_jobs(self, status: JobStatus | None = None, limit: int = 100) -> list[ProofJob]:
        jobs = list(self._jobs.values())
        if status is not None:
            job_ids_with_status = {
                jid for jid, r in self._results.items() if r.status == status
            }
            jobs = [j for j in jobs if j.id in job_ids_with_status]
        return jobs[:limit]

    async def count_by_status(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for r in self._results.values():
            counts[r.status.value] = counts.get(r.status.value, 0) + 1
        return counts


class PostgresJobStore:
    """PostgreSQL-backed job store using SQLAlchemy async sessions.

    Maps between Pydantic domain models and the ZKJobDB SQLAlchemy model.
    """

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    async def save_job(self, job: ProofJob) -> None:
        from carbon_mesh.db.models import ZKJobDB

        async with self._session_factory() as session:
            row = ZKJobDB(
                id=job.id,
                network=job.network.value,
                proof_system=job.proof_system.value,
                circuit_size=job.circuit_size,
                bounty_usd=job.bounty_usd,
                bounty_token=job.bounty_token,
                status=JobStatus.PENDING.value,
                posted_at=job.posted_at,
            )
            session.add(row)
            await session.commit()

    async def save_decision(self, decision: DispatchDecision) -> None:
        from sqlalchemy import update
        from carbon_mesh.db.models import ZKJobDB

        async with self._session_factory() as session:
            stmt = (
                update(ZKJobDB)
                .where(ZKJobDB.id == decision.job_id)
                .values(
                    status=JobStatus.DISPATCHED.value,
                    compute_provider=decision.chosen_provider.provider.value,
                    compute_region=decision.chosen_provider.region,
                    gpu_type=decision.chosen_provider.gpu_type.value,
                    grid_zone=decision.chosen_provider.grid_zone,
                    carbon_intensity_gco2_kwh=decision.chosen_provider.carbon_intensity_gco2_kwh,
                    dispatched_at=decision.dispatched_at,
                )
            )
            await session.execute(stmt)
            await session.commit()

    async def save_result(self, result: JobResult) -> None:
        from sqlalchemy import update
        from carbon_mesh.db.models import ZKJobDB

        async with self._session_factory() as session:
            stmt = (
                update(ZKJobDB)
                .where(ZKJobDB.id == result.job_id)
                .values(
                    status=result.status.value,
                    compute_cost_usd=result.compute_cost_usd,
                    bounty_earned_usd=result.bounty_earned_usd,
                    profit_usd=result.profit_usd,
                    carbon_grams_co2=result.carbon_grams_co2,
                    renewable_percentage=result.renewable_percentage,
                    gpu_seconds=result.gpu_seconds,
                    completed_at=result.completed_at,
                    proof_hash=result.proof_hash,
                    error=result.error,
                )
            )
            await session.execute(stmt)
            await session.commit()

    async def update_status(self, job_id: str, status: JobStatus, error: str = "") -> None:
        from sqlalchemy import update
        from carbon_mesh.db.models import ZKJobDB

        async with self._session_factory() as session:
            values: dict = {"status": status.value}
            if error:
                values["error"] = error
            stmt = update(ZKJobDB).where(ZKJobDB.id == job_id).values(**values)
            await session.execute(stmt)
            await session.commit()

    async def get_job(self, job_id: str) -> ProofJob | None:
        from sqlalchemy import select
        from carbon_mesh.db.models import ZKJobDB

        async with self._session_factory() as session:
            stmt = select(ZKJobDB).where(ZKJobDB.id == job_id)
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row is None:
                return None
            return self._row_to_job(row)

    async def get_decision(self, job_id: str) -> DispatchDecision | None:
        # Decisions are stored as columns on the job row — reconstruct from DB
        return None  # Full reconstruction requires more columns; use in-memory cache

    async def get_result(self, job_id: str) -> JobResult | None:
        from sqlalchemy import select
        from carbon_mesh.db.models import ZKJobDB

        async with self._session_factory() as session:
            stmt = select(ZKJobDB).where(ZKJobDB.id == job_id)
            row = (await session.execute(stmt)).scalar_one_or_none()
            if row is None:
                return None
            return JobResult(
                job_id=row.id,
                status=JobStatus(row.status),
                proof_hash=row.proof_hash or "",
                gpu_seconds=row.gpu_seconds,
                completed_at=row.completed_at,
                compute_cost_usd=row.compute_cost_usd,
                bounty_earned_usd=row.bounty_earned_usd,
                profit_usd=row.profit_usd,
                carbon_grams_co2=row.carbon_grams_co2,
                renewable_percentage=row.renewable_percentage,
                error=row.error or "",
            )

    async def list_jobs(self, status: JobStatus | None = None, limit: int = 100) -> list[ProofJob]:
        from sqlalchemy import select
        from carbon_mesh.db.models import ZKJobDB

        async with self._session_factory() as session:
            stmt = select(ZKJobDB).order_by(ZKJobDB.posted_at.desc()).limit(limit)
            if status is not None:
                stmt = stmt.where(ZKJobDB.status == status.value)
            rows = (await session.execute(stmt)).scalars().all()
            return [self._row_to_job(r) for r in rows]

    async def count_by_status(self) -> dict[str, int]:
        from sqlalchemy import func, select
        from carbon_mesh.db.models import ZKJobDB

        async with self._session_factory() as session:
            stmt = select(ZKJobDB.status, func.count()).group_by(ZKJobDB.status)
            rows = (await session.execute(stmt)).all()
            return {status: count for status, count in rows}

    @staticmethod
    def _row_to_job(row) -> ProofJob:
        from carbon_mesh.models.zk import ProofSystem, ProverNetwork, PROOF_SYSTEM_GPU_MINUTES
        from datetime import timedelta

        ps = ProofSystem(row.proof_system)
        return ProofJob(
            id=row.id,
            network=ProverNetwork(row.network),
            proof_system=ps,
            circuit_size=row.circuit_size,
            input_size_bytes=2 ** row.circuit_size,
            bounty_usd=row.bounty_usd,
            bounty_token=row.bounty_token,
            bounty_amount=row.bounty_usd,
            deadline=row.posted_at + timedelta(minutes=15),
            posted_at=row.posted_at,
            estimated_gpu_minutes=PROOF_SYSTEM_GPU_MINUTES.get(ps, 3.0),
            min_vram_gb=16,
        )
