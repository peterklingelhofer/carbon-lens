"""ZK Proof Job Orchestrator — the core broker logic.

Flow:
1. Poll prover networks for available jobs
2. For each job, query all GPU compute providers
3. Enrich with live carbon intensity data
4. Filter by carbon policy (reject dirty compute)
5. Score remaining options (carbon × cost)
6. Check profitability (bounty - cost > min margin)
7. Dispatch to best option
8. Execute via JobExecutor (provision → prove → verify → submit → claim)
9. Track job lifecycle through completion
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone

from carbon_mesh.carbon_sources.base import CarbonDataSource
from carbon_mesh.grid.mapper import GridMapper
from carbon_mesh.models.zk import (
    BrokerStats,
    CarbonPolicy,
    ComputeOption,
    DispatchDecision,
    GPU_TDP_WATTS,
    JobResult,
    JobStatus,
    ProofJob,
)
from carbon_mesh.zk.compute_providers import MockGPUProvider, enrich_with_carbon
from carbon_mesh.zk.monitoring import BrokerMetrics, broker_metrics
from carbon_mesh.zk.persistence import InMemoryJobStore, JobStore

logger = logging.getLogger(__name__)


class JobOrchestrator:
    """Routes ZK proof jobs to the greenest, most profitable GPU compute."""

    def __init__(
        self,
        carbon_source: CarbonDataSource,
        grid_mapper: GridMapper,
        policy: CarbonPolicy | None = None,
        store: JobStore | None = None,
        metrics: BrokerMetrics | None = None,
    ) -> None:
        self._carbon_source = carbon_source
        self._grid_mapper = grid_mapper
        self._policy = policy or CarbonPolicy()
        self._gpu_provider = MockGPUProvider()
        self._store = store or InMemoryJobStore()
        self._metrics = metrics or broker_metrics

        # In-memory caches (also backed by store for durability)
        self._jobs: dict[str, ProofJob] = {}
        self._decisions: dict[str, DispatchDecision] = {}
        self._results: dict[str, JobResult] = {}

    @property
    def policy(self) -> CarbonPolicy:
        return self._policy

    @policy.setter
    def policy(self, value: CarbonPolicy) -> None:
        self._policy = value

    @property
    def store(self) -> JobStore:
        return self._store

    async def evaluate_job(self, job: ProofJob) -> DispatchDecision | None:
        """Evaluate a proof job and return the optimal dispatch decision.

        Returns None if no green, profitable compute is available.
        """
        self._jobs[job.id] = job
        await self._store.save_job(job)
        self._metrics.record_job_received(job)

        # 1. Get available GPU options
        options = await self._gpu_provider.list_available(
            min_vram_gb=job.min_vram_gb,
        )

        if not options:
            logger.warning("No GPU options available for job %s", job.id)
            result = JobResult(
                job_id=job.id, status=JobStatus.REJECTED, error="No GPU options available"
            )
            self._results[job.id] = result
            await self._store.save_result(result)
            return None

        # 2. Enrich with live carbon data
        options = await enrich_with_carbon(
            options, self._carbon_source, self._grid_mapper
        )

        # 3. Calculate estimated job cost for each option
        for opt in options:
            gpu_hours = job.estimated_gpu_minutes / 60.0
            opt.estimated_job_cost_usd = round(
                opt.cost_per_gpu_hour_usd * gpu_hours * opt.gpu_count, 4
            )

        # 4. Filter by carbon policy
        green_options = self._filter_by_policy(options)
        rejected = [o for o in options if o not in green_options]

        if not green_options:
            logger.info(
                "Job %s rejected: no compute meets carbon policy "
                "(max %s gCO2/kWh, min %s%% renewable)",
                job.id,
                self._policy.max_carbon_intensity_gco2_kwh,
                self._policy.min_renewable_percentage,
            )
            result = JobResult(
                job_id=job.id,
                status=JobStatus.REJECTED,
                error=f"No compute within carbon policy: max {self._policy.max_carbon_intensity_gco2_kwh} gCO2/kWh",
            )
            self._results[job.id] = result
            await self._store.save_result(result)
            return None

        # 5. Filter by profitability
        profitable = [
            o for o in green_options
            if self._is_profitable(job, o)
        ]

        if not profitable:
            cheapest = min(green_options, key=lambda o: o.estimated_job_cost_usd)
            margin = (job.bounty_usd - cheapest.estimated_job_cost_usd) / job.bounty_usd * 100 if job.bounty_usd > 0 else 0
            logger.info(
                "Job %s rejected: best margin %.1f%% < min %.1f%%",
                job.id, margin, self._policy.min_profit_margin_pct,
            )
            result = JobResult(
                job_id=job.id,
                status=JobStatus.REJECTED,
                error=f"Insufficient margin: best {margin:.1f}% < min {self._policy.min_profit_margin_pct}%",
            )
            self._results[job.id] = result
            await self._store.save_result(result)
            return None

        # 6. Score and rank
        scored = self._score_options(job, profitable)
        best = scored[0]

        # 7. Calculate carbon impact
        gpu_hours = job.estimated_gpu_minutes / 60.0
        gpu_kwh = (GPU_TDP_WATTS.get(best.gpu_type, 300) / 1000.0) * gpu_hours
        carbon_grams = gpu_kwh * best.carbon_intensity_gco2_kwh
        # Average grid = ~400 gCO2/kWh globally
        carbon_saved = max(0, gpu_kwh * 400.0 - carbon_grams)

        profit = job.bounty_usd - best.estimated_job_cost_usd
        margin = (profit / job.bounty_usd * 100) if job.bounty_usd > 0 else 0

        decision = DispatchDecision(
            job_id=job.id,
            chosen_provider=best,
            rejected_options=rejected,
            carbon_score=best.carbon_intensity_gco2_kwh / 500.0,  # Normalize
            cost_score=best.estimated_job_cost_usd / job.bounty_usd if job.bounty_usd > 0 else 1.0,
            combined_score=0.0,  # Set below
            estimated_profit_usd=round(profit, 4),
            profit_margin_pct=round(margin, 1),
            carbon_grams_co2=round(carbon_grams, 2),
            carbon_saved_vs_grid_avg_grams=round(carbon_saved, 2),
            dispatched_at=datetime.now(timezone.utc),
        )
        decision.combined_score = round(
            self._policy.carbon_weight * decision.carbon_score
            + self._policy.cost_weight * decision.cost_score,
            4,
        )

        self._decisions[job.id] = decision
        await self._store.save_decision(decision)
        return decision

    async def complete_job(
        self,
        job_id: str,
        success: bool = True,
        proof_hash: str = "",
        gpu_seconds: float = 0,
    ) -> JobResult:
        """Record job completion (or failure)."""
        job = self._jobs.get(job_id)
        decision = self._decisions.get(job_id)

        if not job or not decision:
            return JobResult(
                job_id=job_id,
                status=JobStatus.FAILED,
                error="Job not found",
            )

        now = datetime.now(timezone.utc)
        actual_gpu_hours = gpu_seconds / 3600.0 if gpu_seconds > 0 else job.estimated_gpu_minutes / 60.0
        actual_cost = decision.chosen_provider.cost_per_gpu_hour_usd * actual_gpu_hours

        # Carbon
        gpu_kwh = (GPU_TDP_WATTS.get(decision.chosen_provider.gpu_type, 300) / 1000.0) * actual_gpu_hours
        carbon_grams = gpu_kwh * decision.chosen_provider.carbon_intensity_gco2_kwh

        result = JobResult(
            job_id=job_id,
            status=JobStatus.COMPLETED if success else JobStatus.FAILED,
            proof_hash=proof_hash,
            gpu_seconds=gpu_seconds,
            total_seconds=gpu_seconds + decision.chosen_provider.estimated_startup_seconds,
            completed_at=now,
            compute_cost_usd=round(actual_cost, 4),
            bounty_earned_usd=job.bounty_usd if success else 0,
            profit_usd=round(job.bounty_usd - actual_cost, 4) if success else round(-actual_cost, 4),
            carbon_grams_co2=round(carbon_grams, 2),
            renewable_percentage=decision.chosen_provider.renewable_percentage,
        )
        self._results[job_id] = result
        await self._store.save_result(result)
        self._metrics.record_job_completed(result)
        return result

    def get_stats(self) -> BrokerStats:
        """Aggregate broker statistics."""
        results = list(self._results.values())
        completed = [r for r in results if r.status == JobStatus.COMPLETED]
        failed = [r for r in results if r.status == JobStatus.FAILED]
        rejected = [r for r in results if r.status == JobStatus.REJECTED]

        total_bounties = sum(r.bounty_earned_usd for r in completed)
        total_cost = sum(r.compute_cost_usd for r in completed)
        total_profit = sum(r.profit_usd for r in completed)
        total_carbon = sum(r.carbon_grams_co2 for r in completed)
        total_carbon_saved = sum(
            d.carbon_saved_vs_grid_avg_grams
            for d in self._decisions.values()
            if d.job_id in {r.job_id for r in completed}
        )

        # By network
        jobs_by_network: dict[str, int] = defaultdict(int)
        earnings_by_network: dict[str, float] = defaultdict(float)
        for r in completed:
            job = self._jobs.get(r.job_id)
            if job:
                net = job.network.value
                jobs_by_network[net] += 1
                earnings_by_network[net] += r.bounty_earned_usd

        # By provider
        jobs_by_provider: dict[str, int] = defaultdict(int)
        for d in self._decisions.values():
            if d.job_id in {r.job_id for r in completed}:
                jobs_by_provider[d.chosen_provider.provider.value] += 1

        avg_margin = (total_profit / total_bounties * 100) if total_bounties > 0 else 0
        avg_renewable = (
            sum(r.renewable_percentage for r in completed) / len(completed)
            if completed
            else 0
        )
        zero_carbon_count = sum(1 for r in completed if r.carbon_grams_co2 == 0)
        zero_carbon_pct = (zero_carbon_count / len(completed) * 100) if completed else 0

        return BrokerStats(
            total_jobs=len(results),
            completed_jobs=len(completed),
            failed_jobs=len(failed),
            rejected_jobs=len(rejected),
            active_jobs=len(self._jobs) - len(results),
            total_bounties_earned_usd=round(total_bounties, 2),
            total_compute_cost_usd=round(total_cost, 2),
            total_profit_usd=round(total_profit, 2),
            avg_profit_margin_pct=round(avg_margin, 1),
            total_carbon_grams_co2=round(total_carbon, 2),
            total_carbon_saved_grams=round(total_carbon_saved, 2),
            avg_renewable_percentage=round(avg_renewable, 1),
            zero_carbon_job_pct=round(zero_carbon_pct, 1),
            jobs_by_network=dict(jobs_by_network),
            jobs_by_provider=dict(jobs_by_provider),
            earnings_by_network={k: round(v, 2) for k, v in earnings_by_network.items()},
        )

    def _filter_by_policy(self, options: list[ComputeOption]) -> list[ComputeOption]:
        """Filter compute options by carbon policy."""
        filtered: list[ComputeOption] = []
        for opt in options:
            if opt.carbon_intensity_gco2_kwh > self._policy.max_carbon_intensity_gco2_kwh:
                continue
            if opt.renewable_percentage < self._policy.min_renewable_percentage:
                continue
            filtered.append(opt)

        # Sort: behind-the-meter first if preferred
        if self._policy.prefer_behind_the_meter:
            filtered.sort(key=lambda o: (not o.is_behind_the_meter, o.carbon_intensity_gco2_kwh))

        return filtered

    def _is_profitable(self, job: ProofJob, option: ComputeOption) -> bool:
        """Check if a job is profitable with a given compute option."""
        if job.bounty_usd <= 0:
            return False
        profit = job.bounty_usd - option.estimated_job_cost_usd
        margin = profit / job.bounty_usd * 100
        return margin >= self._policy.min_profit_margin_pct

    def _score_options(
        self, job: ProofJob, options: list[ComputeOption]
    ) -> list[ComputeOption]:
        """Score and rank compute options by carbon + cost composite."""
        if not options:
            return []

        # Normalize carbon: 0 = best (zero carbon), 1 = worst
        max_carbon = max(o.carbon_intensity_gco2_kwh for o in options) or 1.0
        # Normalize cost: 0 = cheapest, 1 = most expensive
        max_cost = max(o.estimated_job_cost_usd for o in options) or 1.0

        def score(opt: ComputeOption) -> float:
            carbon_norm = opt.carbon_intensity_gco2_kwh / max_carbon if max_carbon > 0 else 0
            cost_norm = opt.estimated_job_cost_usd / max_cost if max_cost > 0 else 0
            # Bonus for behind-the-meter
            btm_bonus = -0.1 if opt.is_behind_the_meter else 0
            return (
                self._policy.carbon_weight * carbon_norm
                + self._policy.cost_weight * cost_norm
                + btm_bonus
            )

        return sorted(options, key=score)
