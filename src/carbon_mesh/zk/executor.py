"""Job executor — the full pipeline from dispatch decision to bounty claimed.

Ties together all components:
  1. GPU lifecycle manager (provision → run → terminate)
  2. Prover runtime (Docker image selection, witness prep)
  3. Proof verification (local check before submission)
  4. Wallet (submit proof, claim bounty)
  5. Persistence (durable job state)
  6. Monitoring (metrics, events)

The executor runs asynchronously, processing one job at a time
or concurrently (with configurable parallelism).
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from carbon_mesh.models.zk import (
    CarbonPolicy,
    DispatchDecision,
    GPUInstance,
    InstanceStatus,
    JobResult,
    JobStatus,
    ProofJob,
)

if TYPE_CHECKING:
    from carbon_mesh.models.zk import ComputeOption
from carbon_mesh.zk.gpu_lifecycle import ComputeBackend, LocalDockerBackend
from carbon_mesh.zk.monitoring import BrokerMetrics, broker_metrics
from carbon_mesh.zk.persistence import InMemoryJobStore, JobStore
from carbon_mesh.zk.prover_runtime import ProverRuntime
from carbon_mesh.zk.verification import ProofVerifier
from carbon_mesh.zk.wallet import LocalWallet, WalletBackend

logger = logging.getLogger(__name__)


class JobExecutor:
    """Executes ZK proof jobs end-to-end: provision → prove → verify → submit → claim.

    Usage:
        executor = JobExecutor()
        result = await executor.execute(job, decision)
    """

    def __init__(
        self,
        compute_backend: ComputeBackend | None = None,
        prover_runtime: ProverRuntime | None = None,
        verifier: ProofVerifier | None = None,
        wallet: WalletBackend | None = None,
        store: JobStore | None = None,
        metrics: BrokerMetrics | None = None,
        max_concurrent_jobs: int = 4,
        auto_claim_bounty: bool = True,
        max_retries: int = 2,
        carbon_policy: CarbonPolicy | None = None,
    ) -> None:
        self._compute = compute_backend or LocalDockerBackend()
        self._runtime = prover_runtime or ProverRuntime()
        self._verifier = verifier or ProofVerifier()
        self._wallet = wallet or LocalWallet()
        self._store = store or InMemoryJobStore()
        self._metrics = metrics or broker_metrics
        self._semaphore = asyncio.Semaphore(max_concurrent_jobs)
        self._auto_claim = auto_claim_bounty
        self._max_retries = max_retries
        self._policy = carbon_policy or CarbonPolicy()

        # Active jobs tracking
        self._active_jobs: dict[str, GPUInstance] = {}
        self._running = False

    @property
    def policy(self) -> CarbonPolicy:
        return self._policy

    @policy.setter
    def policy(self, value: CarbonPolicy) -> None:
        self._policy = value

    async def execute(self, job: ProofJob, decision: DispatchDecision) -> JobResult:
        """Execute a single proof job through the full pipeline.

        Includes automatic retry on spot instance interruptions —
        if a GPU is preempted mid-proof, the job is retried on the
        next available green compute option (up to max_retries).

        Steps:
        1. Persist job state as DISPATCHED
        2. Provision GPU instance
        3. Run prover container
        4. Verify proof locally
        5. Submit proof on-chain
        6. Claim bounty
        7. Terminate GPU instance
        8. Record final result
        """
        async with self._semaphore:
            result = await self._execute_inner(job, decision)

            # Retry on infrastructure failures (spot interruption, OOM, etc.)
            retries = 0
            while (
                result.status == JobStatus.FAILED
                and retries < self._max_retries
                and self._is_retryable(result.error)
                and self._has_time_remaining(job)
            ):
                retries += 1
                logger.warning(
                    "Retrying job %s (attempt %d/%d): %s",
                    job.id,
                    retries + 1,
                    self._max_retries + 1,
                    result.error,
                )
                result = await self._execute_inner(job, decision)

            return result

    def _check_carbon_compliance(self, provider: ComputeOption) -> bool:
        """Verify a compute option still meets carbon policy.

        Called immediately before GPU provisioning to catch policy changes
        that occurred between evaluation and execution.
        """
        if provider.carbon_intensity_gco2_kwh > self._policy.max_carbon_intensity_gco2_kwh:
            logger.warning(
                "Carbon compliance BLOCKED: %s/%s has %.1f gCO2/kWh > max %.1f",
                provider.provider.value,
                provider.region,
                provider.carbon_intensity_gco2_kwh,
                self._policy.max_carbon_intensity_gco2_kwh,
            )
            return False
        if provider.renewable_percentage < self._policy.min_renewable_percentage:
            logger.warning(
                "Carbon compliance BLOCKED: %s/%s has %.1f%% renewable < min %.1f%%",
                provider.provider.value,
                provider.region,
                provider.renewable_percentage,
                self._policy.min_renewable_percentage,
            )
            return False
        if self._policy.require_behind_the_meter and not provider.is_behind_the_meter:
            logger.warning(
                "Carbon compliance BLOCKED: %s/%s is not behind-the-meter (required by policy)",
                provider.provider.value,
                provider.region,
            )
            return False
        return True

    @staticmethod
    def _is_retryable(error: str) -> bool:
        """Determine if a failure is retryable (infrastructure vs. logic error)."""
        # Carbon policy violations are NEVER retryable
        if "carbon policy violation" in error.lower():
            return False
        retryable_patterns = [
            "Instance failed to start",
            "Prover produced no output",
            "container failed",
            "SSH not ready",
            "Connection refused",
            "timeout",
            "preempted",
            "interrupted",
            "OOM",
            "out of memory",
        ]
        error_lower = error.lower()
        return any(p.lower() in error_lower for p in retryable_patterns)

    @staticmethod
    def _has_time_remaining(job: ProofJob) -> bool:
        """Check if there's enough time to retry before the deadline."""
        remaining = (job.deadline - datetime.now(timezone.utc)).total_seconds()
        # Need at least 3 minutes for a retry attempt
        return remaining > 180

    async def _execute_inner(self, job: ProofJob, decision: DispatchDecision) -> JobResult:
        start_time = time.monotonic()
        instance: GPUInstance | None = None
        result: JobResult

        try:
            # 0. Re-validate carbon policy (may have tightened since evaluation)
            provider = decision.chosen_provider
            if not self._check_carbon_compliance(provider):
                raise RuntimeError(
                    f"Carbon policy violation: {provider.provider.value}/{provider.region} "
                    f"has {provider.carbon_intensity_gco2_kwh} gCO2/kWh, "
                    f"{provider.renewable_percentage}% renewable, "
                    f"BTM={provider.is_behind_the_meter} — "
                    f"policy requires ≤{self._policy.max_carbon_intensity_gco2_kwh} gCO2/kWh, "
                    f"≥{self._policy.min_renewable_percentage}% renewable"
                    + (", BTM only" if self._policy.require_behind_the_meter else "")
                )

            # 1. Update status to DISPATCHED
            await self._store.update_status(job.id, JobStatus.DISPATCHED)
            self._metrics.record_dispatch(job, decision)

            # 2. Provision GPU
            logger.info(
                "Provisioning GPU for job %s on %s/%s",
                job.id,
                decision.chosen_provider.provider.value,
                decision.chosen_provider.region,
            )
            instance = await self._compute.provision(decision.chosen_provider, job.id)
            self._active_jobs[job.id] = instance

            # 3. Wait for instance to be ready
            instance = await self._compute.wait_ready(instance)
            if instance.status != InstanceStatus.RUNNING:
                raise RuntimeError(f"Instance failed to start: {instance.status}")

            # 4. Get prover Docker image config
            image = self._runtime.get_image_for_job(job)

            # 5. Prepare witness data
            # In production, witness data comes from the prover network
            # For now, create a placeholder based on job metadata
            witness_data = self._runtime.prepare_witness_data(job, b"\x00" * job.input_size_bytes)

            # 6. Run prover container
            await self._store.update_status(job.id, JobStatus.PROVING)
            logger.info("Running prover for job %s: %s", job.id, image.image)

            artifact = await self._compute.run_container(instance, image, witness_data)
            self._metrics.record_proof_generated(artifact)

            if not artifact.proof_data:
                raise RuntimeError("Prover produced no output")

            # 7. Verify proof locally
            logger.info("Verifying proof for job %s (%d bytes)", job.id, artifact.proof_size_bytes)
            verification = await self._verifier.verify(artifact)
            self._metrics.record_verification(verification)

            if not verification.valid:
                raise RuntimeError(f"Proof verification failed: {verification.error}")

            # 8. Submit proof on-chain
            await self._store.update_status(job.id, JobStatus.SUBMITTING)
            gas_cost_usd = await self._wallet.estimate_gas(job.network, artifact.proof_size_bytes)
            submit_receipt = await self._wallet.submit_proof(
                job.network,
                job.id,
                artifact.proof_data,
            )
            self._metrics.record_submission(job.id, submit_receipt.tx_hash, gas_cost_usd)

            # 9. Claim bounty (if auto-claim enabled)
            bounty_earned = job.bounty_usd
            if self._auto_claim:
                await self._wallet.claim_bounty(
                    job.network,
                    job.id,
                    submit_receipt.tx_hash,
                )
                self._metrics.record_bounty_claimed(job.id, bounty_earned)

            # 10. Calculate final result
            elapsed = time.monotonic() - start_time
            gpu_seconds = artifact.generation_gpu_seconds
            compute_cost = decision.chosen_provider.cost_per_gpu_hour_usd * (gpu_seconds / 3600.0)
            total_cost = compute_cost + gas_cost_usd
            profit = bounty_earned - total_cost

            result = JobResult(
                job_id=job.id,
                status=JobStatus.COMPLETED,
                proof_hash=artifact.proof_hash,
                proof_size_bytes=artifact.proof_size_bytes,
                verification_tx=submit_receipt.tx_hash,
                gpu_seconds=gpu_seconds,
                total_seconds=elapsed,
                started_at=instance.started_at or datetime.now(timezone.utc),
                completed_at=datetime.now(timezone.utc),
                compute_cost_usd=round(compute_cost, 4),
                bounty_earned_usd=round(bounty_earned, 4),
                profit_usd=round(profit, 4),
                carbon_grams_co2=decision.carbon_grams_co2,
                renewable_percentage=decision.chosen_provider.renewable_percentage,
            )

            logger.info(
                "Job %s completed: profit=$%.4f, carbon=%.2fg CO2, gpu=%.1fs",
                job.id,
                profit,
                decision.carbon_grams_co2,
                gpu_seconds,
            )

        except Exception as e:
            elapsed = time.monotonic() - start_time
            logger.error("Job %s failed: %s", job.id, e)

            result = JobResult(
                job_id=job.id,
                status=JobStatus.FAILED,
                total_seconds=elapsed,
                completed_at=datetime.now(timezone.utc),
                error=str(e),
            )

        finally:
            # Always terminate the GPU instance
            if instance:
                try:
                    await self._compute.terminate(instance)
                except Exception as e:
                    logger.warning("Failed to terminate instance for job %s: %s", job.id, e)
                self._active_jobs.pop(job.id, None)

        # Persist and record
        await self._store.save_result(result)
        self._metrics.record_job_completed(result)
        if result.status == JobStatus.COMPLETED:
            self._metrics.record_carbon_saved(decision)

        return result

    async def execute_batch(self, jobs: list[tuple[ProofJob, DispatchDecision]]) -> list[JobResult]:
        """Execute multiple jobs concurrently (up to max_concurrent_jobs)."""
        tasks = [self.execute(job, decision) for job, decision in jobs]
        return await asyncio.gather(*tasks)

    def get_active_jobs(self) -> dict[str, GPUInstance]:
        """Get currently executing jobs and their GPU instances."""
        return dict(self._active_jobs)

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job and terminate its GPU instance."""
        instance = self._active_jobs.get(job_id)
        if not instance:
            return False

        try:
            await self._compute.terminate(instance)
            self._active_jobs.pop(job_id, None)
            await self._store.update_status(job_id, JobStatus.FAILED, error="Cancelled by user")
            logger.info("Cancelled job %s", job_id)
            return True
        except Exception as e:
            logger.error("Failed to cancel job %s: %s", job_id, e)
            return False
