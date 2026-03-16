"""ZK Broker monitoring — Prometheus metrics, structured events, and alerting.

Tracks key operational metrics:
  - Job throughput and latency (by network, status)
  - Revenue and profit (by network, provider)
  - Carbon impact (emissions, savings)
  - GPU utilization and cost efficiency
  - Error rates and failure modes

Integrates with the existing Prometheus instrumentator in main.py.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import datetime, timezone

from carbon_mesh.models.zk import (
    DispatchDecision,
    JobEvent,
    JobResult,
    JobStatus,
    ProofArtifact,
    ProofJob,
    VerificationResult,
)

logger = logging.getLogger(__name__)


class BrokerMetrics:
    """Collects and exposes ZK broker metrics.

    In-process metrics collector that works both standalone (for testing)
    and alongside Prometheus (for production).
    """

    def __init__(self) -> None:
        # Counters
        self.jobs_received: int = 0
        self.jobs_dispatched: int = 0
        self.jobs_completed: int = 0
        self.jobs_failed: int = 0
        self.jobs_rejected: int = 0
        self.proofs_verified: int = 0
        self.proofs_submitted: int = 0
        self.bounties_claimed: int = 0

        # Revenue tracking
        self.total_bounties_usd: float = 0.0
        self.total_compute_cost_usd: float = 0.0
        self.total_gas_cost_usd: float = 0.0
        self.total_profit_usd: float = 0.0

        # Carbon tracking
        self.total_carbon_grams: float = 0.0
        self.total_carbon_saved_grams: float = 0.0

        # Latency tracking (rolling window)
        self._proving_times: list[float] = []
        self._submission_times: list[float] = []

        # By-network breakdown
        self.jobs_by_network: dict[str, int] = defaultdict(int)
        self.revenue_by_network: dict[str, float] = defaultdict(float)
        self.jobs_by_provider: dict[str, int] = defaultdict(int)

        # Event log (bounded)
        self._events: list[JobEvent] = []
        self._max_events = 10_000

    def record_job_received(self, job: ProofJob) -> None:
        self.jobs_received += 1
        self.jobs_by_network[job.network.value] += 1
        self._emit_event(job.id, "job_received", {
            "network": job.network.value,
            "bounty_usd": job.bounty_usd,
            "proof_system": job.proof_system.value,
            "circuit_size": job.circuit_size,
        })

    def record_dispatch(self, job: ProofJob, decision: DispatchDecision) -> None:
        self.jobs_dispatched += 1
        self.jobs_by_provider[decision.chosen_provider.provider.value] += 1
        self._emit_event(job.id, "dispatched", {
            "provider": decision.chosen_provider.provider.value,
            "region": decision.chosen_provider.region,
            "estimated_profit": decision.estimated_profit_usd,
            "carbon_grams": decision.carbon_grams_co2,
        })

    def record_proof_generated(self, artifact: ProofArtifact) -> None:
        self._proving_times.append(artifact.generation_gpu_seconds)
        # Keep last 1000 timing samples
        if len(self._proving_times) > 1000:
            self._proving_times = self._proving_times[-1000:]
        self._emit_event(artifact.job_id, "proof_generated", {
            "gpu_seconds": artifact.generation_gpu_seconds,
            "proof_size_bytes": artifact.proof_size_bytes,
        })

    def record_verification(self, result: VerificationResult) -> None:
        self.proofs_verified += 1
        self._emit_event(result.job_id, "proof_verified", {
            "valid": result.valid,
            "verifier": result.verifier,
            "time_ms": result.verification_time_ms,
        })

    def record_submission(self, job_id: str, tx_hash: str, gas_cost_usd: float) -> None:
        self.proofs_submitted += 1
        self.total_gas_cost_usd += gas_cost_usd
        self._emit_event(job_id, "proof_submitted", {
            "tx_hash": tx_hash,
            "gas_cost_usd": gas_cost_usd,
        })

    def record_bounty_claimed(self, job_id: str, bounty_usd: float) -> None:
        self.bounties_claimed += 1
        self.total_bounties_usd += bounty_usd
        self._emit_event(job_id, "bounty_claimed", {"bounty_usd": bounty_usd})

    def record_job_completed(self, result: JobResult) -> None:
        if result.status == JobStatus.COMPLETED:
            self.jobs_completed += 1
            self.total_compute_cost_usd += result.compute_cost_usd
            self.total_profit_usd += result.profit_usd
            self.total_carbon_grams += result.carbon_grams_co2
        elif result.status == JobStatus.FAILED:
            self.jobs_failed += 1
        elif result.status == JobStatus.REJECTED:
            self.jobs_rejected += 1

        self._emit_event(result.job_id, "job_completed", {
            "status": result.status.value,
            "profit_usd": result.profit_usd,
            "carbon_grams": result.carbon_grams_co2,
        })

    def record_carbon_saved(self, decision: DispatchDecision) -> None:
        self.total_carbon_saved_grams += decision.carbon_saved_vs_grid_avg_grams

    def get_summary(self) -> dict:
        """Get a summary of all metrics for the /stats endpoint."""
        avg_proving = (
            sum(self._proving_times) / len(self._proving_times)
            if self._proving_times else 0.0
        )
        p95_proving = (
            sorted(self._proving_times)[int(len(self._proving_times) * 0.95)]
            if len(self._proving_times) > 10 else 0.0
        )

        return {
            "jobs": {
                "received": self.jobs_received,
                "dispatched": self.jobs_dispatched,
                "completed": self.jobs_completed,
                "failed": self.jobs_failed,
                "rejected": self.jobs_rejected,
                "success_rate_pct": round(
                    self.jobs_completed / max(1, self.jobs_dispatched) * 100, 1
                ),
            },
            "revenue": {
                "total_bounties_usd": round(self.total_bounties_usd, 2),
                "total_compute_cost_usd": round(self.total_compute_cost_usd, 2),
                "total_gas_cost_usd": round(self.total_gas_cost_usd, 2),
                "total_profit_usd": round(self.total_profit_usd, 2),
                "net_margin_pct": round(
                    self.total_profit_usd / max(0.01, self.total_bounties_usd) * 100, 1
                ),
            },
            "carbon": {
                "total_emissions_grams": round(self.total_carbon_grams, 2),
                "total_saved_grams": round(self.total_carbon_saved_grams, 2),
                "savings_ratio": round(
                    self.total_carbon_saved_grams / max(0.01, self.total_carbon_grams + self.total_carbon_saved_grams), 2
                ),
            },
            "performance": {
                "avg_proving_seconds": round(avg_proving, 1),
                "p95_proving_seconds": round(p95_proving, 1),
                "proofs_verified": self.proofs_verified,
                "proofs_submitted": self.proofs_submitted,
            },
            "by_network": dict(self.jobs_by_network),
            "revenue_by_network": {k: round(v, 2) for k, v in self.revenue_by_network.items()},
            "by_provider": dict(self.jobs_by_provider),
        }

    def get_recent_events(self, limit: int = 100) -> list[JobEvent]:
        """Get recent job events for the activity feed."""
        return self._events[-limit:]

    def _emit_event(self, job_id: str, event_type: str, details: dict) -> None:
        event = JobEvent(
            job_id=job_id,
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            details=details,
        )
        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events:]

        # Also log as structured event
        logger.info(
            "ZK event: %s job=%s %s",
            event_type, job_id[:12], details,
        )


# Module-level singleton for use across the broker
broker_metrics = BrokerMetrics()
