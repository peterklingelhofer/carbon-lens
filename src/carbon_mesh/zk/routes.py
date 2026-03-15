"""ZK Broker API endpoints — job submission, status, stats, policy config."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from carbon_mesh.api.deps import get_carbon_source, get_grid_mapper
from carbon_mesh.models.zk import (
    BrokerStats,
    CarbonPolicy,
    ComputeOption,
    DispatchDecision,
    JobResult,
    ProofJob,
    ProverNetwork,
)
from carbon_mesh.zk.orchestrator import JobOrchestrator
from carbon_mesh.zk.prover_networks import MockProverNetwork

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/zk", tags=["ZK Broker"])

# Singleton orchestrator (production would use DI)
_orchestrator: JobOrchestrator | None = None


def _get_orchestrator() -> JobOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = JobOrchestrator(
            carbon_source=get_carbon_source(),
            grid_mapper=get_grid_mapper(),
        )
    return _orchestrator


# --- Request/response models ---


class EvaluateResponse(BaseModel):
    decision: DispatchDecision | None
    rejected: bool
    rejection_reason: str = ""


class SimulateRequest(BaseModel):
    """Simulate the broker's routing for a hypothetical job."""

    network: ProverNetwork = ProverNetwork.BOUNDLESS
    bounty_usd: float = 5.0
    circuit_size: int = 20
    min_vram_gb: int = 16
    max_carbon_intensity: float | None = None


class SimulateResponse(BaseModel):
    job: ProofJob
    decision: DispatchDecision | None
    all_options: list[ComputeOption]
    green_options: list[ComputeOption]
    rejected: bool
    rejection_reason: str = ""


# --- Endpoints ---


@router.get("/jobs/available", response_model=list[ProofJob])
async def list_available_jobs(
    network: ProverNetwork | None = None,
) -> list[ProofJob]:
    """Poll prover networks for available proof jobs."""
    networks = [network] if network else list(ProverNetwork)

    all_jobs: list[ProofJob] = []
    for net in networks:
        adapter = MockProverNetwork(net)
        jobs = await adapter.fetch_available_jobs()
        all_jobs.extend(jobs)

    return all_jobs


@router.post("/jobs/evaluate", response_model=EvaluateResponse)
async def evaluate_job(job: ProofJob) -> EvaluateResponse:
    """Evaluate a proof job and return the optimal green dispatch decision."""
    orchestrator = _get_orchestrator()
    decision = await orchestrator.evaluate_job(job)

    if decision is None:
        result = orchestrator._results.get(job.id)
        reason = result.error if result else "Unknown"
        return EvaluateResponse(decision=None, rejected=True, rejection_reason=reason)

    return EvaluateResponse(decision=decision, rejected=False)


@router.post("/jobs/{job_id}/complete", response_model=JobResult)
async def complete_job(
    job_id: str,
    success: bool = True,
    gpu_seconds: float = 0,
) -> JobResult:
    """Record job completion or failure."""
    orchestrator = _get_orchestrator()
    return await orchestrator.complete_job(
        job_id=job_id,
        success=success,
        gpu_seconds=gpu_seconds,
        proof_hash=f"0x{'a' * 64}",
    )


@router.post("/simulate", response_model=SimulateResponse)
async def simulate_routing(req: SimulateRequest) -> SimulateResponse:
    """Simulate the broker's green routing for a hypothetical job.

    Great for demos — shows which compute providers are available,
    which pass the carbon filter, and which one wins.
    """
    from carbon_mesh.models.zk import ProofSystem, PROOF_SYSTEM_GPU_MINUTES
    import uuid

    now = datetime.now(timezone.utc)
    job = ProofJob(
        id=f"sim-{uuid.uuid4().hex[:8]}",
        network=req.network,
        proof_system=ProofSystem.RISC_ZERO,
        circuit_size=req.circuit_size,
        input_size_bytes=2 ** req.circuit_size,
        bounty_usd=req.bounty_usd,
        bounty_token="USDC",
        bounty_amount=req.bounty_usd,
        deadline=now,
        posted_at=now,
        estimated_gpu_minutes=PROOF_SYSTEM_GPU_MINUTES[ProofSystem.RISC_ZERO] * (2 ** (req.circuit_size - 20)),
        min_vram_gb=req.min_vram_gb,
    )

    orchestrator = _get_orchestrator()

    # Temporarily override policy if custom threshold provided
    original_policy = orchestrator.policy
    if req.max_carbon_intensity is not None:
        orchestrator.policy = original_policy.model_copy(
            update={"max_carbon_intensity_gco2_kwh": req.max_carbon_intensity}
        )

    # Get all options before filtering
    from carbon_mesh.zk.compute_providers import MockGPUProvider, enrich_with_carbon

    all_options = await MockGPUProvider().list_available(min_vram_gb=req.min_vram_gb)
    all_options = await enrich_with_carbon(
        all_options, get_carbon_source(), get_grid_mapper()
    )

    # Calculate costs
    for opt in all_options:
        gpu_hours = job.estimated_gpu_minutes / 60.0
        opt.estimated_job_cost_usd = round(
            opt.cost_per_gpu_hour_usd * gpu_hours * opt.gpu_count, 4
        )

    # Filter green
    green_options = orchestrator._filter_by_policy(all_options)

    # Evaluate
    decision = await orchestrator.evaluate_job(job)

    # Restore policy
    orchestrator.policy = original_policy

    rejected = decision is None
    reason = ""
    if rejected:
        result = orchestrator._results.get(job.id)
        reason = result.error if result else "Unknown"

    return SimulateResponse(
        job=job,
        decision=decision,
        all_options=all_options,
        green_options=green_options,
        rejected=rejected,
        rejection_reason=reason,
    )


@router.get("/stats", response_model=BrokerStats)
async def broker_stats() -> BrokerStats:
    """Get aggregate broker statistics."""
    orchestrator = _get_orchestrator()
    return orchestrator.get_stats()


@router.get("/policy", response_model=CarbonPolicy)
async def get_policy() -> CarbonPolicy:
    """Get current carbon routing policy."""
    return _get_orchestrator().policy


@router.put("/policy", response_model=CarbonPolicy)
async def update_policy(policy: CarbonPolicy) -> CarbonPolicy:
    """Update carbon routing policy."""
    orchestrator = _get_orchestrator()
    orchestrator.policy = policy
    logger.info(
        "Carbon policy updated: max_intensity=%s, min_renewable=%s%%",
        policy.max_carbon_intensity_gco2_kwh,
        policy.min_renewable_percentage,
    )
    return policy


@router.get("/compute/available", response_model=list[ComputeOption])
async def list_compute(min_vram_gb: int = 0) -> list[ComputeOption]:
    """List all available GPU compute options with live carbon data."""
    from carbon_mesh.zk.compute_providers import MockGPUProvider, enrich_with_carbon

    options = await MockGPUProvider().list_available(min_vram_gb=min_vram_gb)
    return await enrich_with_carbon(
        options, get_carbon_source(), get_grid_mapper()
    )
