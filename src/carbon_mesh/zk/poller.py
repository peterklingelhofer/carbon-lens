"""Background job poller — continuously fetches available proof jobs from all prover networks.

Runs as an asyncio background task during the FastAPI lifespan.
Polls all configured prover networks, evaluates profitability,
and auto-dispatches profitable jobs to green compute.

This is the "autopilot" mode — the broker earns bounties 24/7
without manual intervention.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from carbon_mesh.models.zk import ProverNetwork
from carbon_mesh.zk.monitoring import broker_metrics
from carbon_mesh.zk.prover_networks import MockProverNetwork

logger = logging.getLogger(__name__)


class JobPoller:
    """Polls prover networks for available jobs and auto-routes profitable ones."""

    def __init__(
        self,
        orchestrator,  # JobOrchestrator (avoid circular import)
        executor=None,  # JobExecutor (optional — if None, evaluate-only mode)
        poll_interval_seconds: float = 15.0,
        auto_execute: bool = False,
        networks: list[ProverNetwork] | None = None,
    ) -> None:
        self._orchestrator = orchestrator
        self._executor = executor
        self._interval = poll_interval_seconds
        self._auto_execute = auto_execute and executor is not None
        self._networks = networks or list(ProverNetwork)
        self._running = False
        self._task: asyncio.Task | None = None
        self._seen_job_ids: set[str] = set()
        self._max_seen = 10_000  # Prevent unbounded memory

        # Stats
        self.polls_completed: int = 0
        self.jobs_discovered: int = 0
        self.jobs_auto_dispatched: int = 0

    async def start(self) -> None:
        """Start the background polling loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info(
            "Job poller started: %d networks, %ds interval, auto_execute=%s",
            len(self._networks), self._interval, self._auto_execute,
        )

    async def stop(self) -> None:
        """Stop the polling loop gracefully."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Job poller stopped after %d polls", self.polls_completed)

    async def _poll_loop(self) -> None:
        """Main polling loop — runs until stopped."""
        while self._running:
            try:
                await self._poll_once()
            except Exception as e:
                logger.error("Poll cycle failed: %s", e)
            await asyncio.sleep(self._interval)

    async def _poll_once(self) -> None:
        """Single poll cycle — fetch jobs from all networks and evaluate."""
        all_jobs = []
        for network in self._networks:
            try:
                adapter = MockProverNetwork(network)
                jobs = await adapter.fetch_available_jobs()
                all_jobs.extend(jobs)
            except Exception as e:
                logger.warning("Failed to poll %s: %s", network.value, e)

        self.polls_completed += 1

        # Filter out jobs we've already seen
        new_jobs = [j for j in all_jobs if j.id not in self._seen_job_ids]
        if not new_jobs:
            return

        self.jobs_discovered += len(new_jobs)
        for job in new_jobs:
            self._seen_job_ids.add(job.id)

        # Prune seen set if it gets too large
        if len(self._seen_job_ids) > self._max_seen:
            self._seen_job_ids = set(list(self._seen_job_ids)[-5000:])

        logger.info("Discovered %d new jobs across %d networks", len(new_jobs), len(self._networks))

        # Evaluate each job
        for job in new_jobs:
            try:
                decision = await self._orchestrator.evaluate_job(job)
                if decision is None:
                    continue

                if self._auto_execute and self._executor:
                    # Auto-dispatch to green compute
                    self.jobs_auto_dispatched += 1
                    asyncio.create_task(
                        self._execute_with_logging(job, decision)
                    )
                else:
                    logger.info(
                        "Job %s profitable on %s (profit=$%.2f, margin=%.1f%%) — awaiting manual dispatch",
                        job.id,
                        decision.chosen_provider.provider.value,
                        decision.estimated_profit_usd,
                        decision.profit_margin_pct,
                    )
            except Exception as e:
                logger.error("Failed to evaluate job %s: %s", job.id, e)

    async def _execute_with_logging(self, job, decision) -> None:
        """Execute a job and log the result."""
        try:
            result = await self._executor.execute(job, decision)
            if result.status.value == "completed":
                logger.info(
                    "Auto-executed job %s: profit=$%.4f, carbon=%.2fg CO2",
                    job.id, result.profit_usd, result.carbon_grams_co2,
                )
            else:
                logger.warning("Auto-executed job %s failed: %s", job.id, result.error)
        except Exception as e:
            logger.error("Auto-execution failed for job %s: %s", job.id, e)

    def get_status(self) -> dict:
        """Get poller status for the /status endpoint."""
        return {
            "running": self._running,
            "poll_interval_seconds": self._interval,
            "auto_execute": self._auto_execute,
            "networks": [n.value for n in self._networks],
            "polls_completed": self.polls_completed,
            "jobs_discovered": self.jobs_discovered,
            "jobs_auto_dispatched": self.jobs_auto_dispatched,
            "seen_job_ids_count": len(self._seen_job_ids),
        }
