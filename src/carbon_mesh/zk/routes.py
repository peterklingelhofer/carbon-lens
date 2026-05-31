"""ZK Broker API endpoints — job submission, execution, status, stats, policy config."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from carbon_mesh.api.deps import get_carbon_source, get_grid_mapper
from carbon_mesh.auth.dependencies import require_api_key
from carbon_mesh.models.zk import (
    BrokerStats,
    CarbonPolicy,
    ComputeOption,
    DispatchDecision,
    JobEvent,
    JobResult,
    ProofJob,
    ProverNetwork,
    SpotPriceQuote,
    WalletInfo,
)
from carbon_mesh.zk.monitoring import broker_metrics
from carbon_mesh.zk.orchestrator import JobOrchestrator
from carbon_mesh.zk.prover_networks import MockProverNetwork

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/v1/zk",
    tags=["ZK Broker"],
    dependencies=[Depends(require_api_key)],
)

# Singleton orchestrator (production would use DI)
_orchestrator: JobOrchestrator | None = None
_executor = None
_spot_feed = None
_wallet = None
_poller = None


def _policy_from_config() -> CarbonPolicy:
    """Build CarbonPolicy from environment variables."""
    from carbon_mesh.config import settings

    return CarbonPolicy(
        max_carbon_intensity_gco2_kwh=settings.zk_max_carbon_intensity,
        min_renewable_percentage=settings.zk_min_renewable_pct,
        require_behind_the_meter=settings.zk_require_behind_the_meter,
        prefer_behind_the_meter=settings.zk_prefer_behind_the_meter,
        carbon_weight=settings.zk_carbon_weight,
        cost_weight=settings.zk_cost_weight,
        min_profit_margin_pct=settings.zk_min_profit_margin_pct,
    )


def _get_orchestrator() -> JobOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = JobOrchestrator(
            carbon_source=get_carbon_source(),
            grid_mapper=get_grid_mapper(),
            policy=_policy_from_config(),
        )
    return _orchestrator


def _get_executor():
    global _executor
    if _executor is None:
        from carbon_mesh.zk.executor import JobExecutor

        orchestrator = _get_orchestrator()
        _executor = JobExecutor(
            store=orchestrator.store,
            metrics=broker_metrics,
            carbon_policy=orchestrator.policy,
        )
    return _executor


def _get_spot_feed():
    global _spot_feed
    if _spot_feed is None:
        from carbon_mesh.zk.spot_prices import SpotPriceFeed

        _spot_feed = SpotPriceFeed()
    return _spot_feed


def _get_wallet():
    global _wallet
    if _wallet is None:
        from carbon_mesh.zk.wallet import LocalWallet

        _wallet = LocalWallet()
    return _wallet


# --- Request/response models ---


class EvaluateResponse(BaseModel):
    decision: DispatchDecision | None
    rejected: bool
    rejection_reason: str = ""


class ExecuteRequest(BaseModel):
    """Submit a job for full execution (evaluate + prove + submit)."""

    job: ProofJob


class ExecuteResponse(BaseModel):
    decision: DispatchDecision | None
    result: JobResult | None
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


@router.post("/jobs/execute", response_model=ExecuteResponse)
async def execute_job(req: ExecuteRequest) -> ExecuteResponse:
    """Evaluate and execute a proof job end-to-end.

    Full pipeline: evaluate → provision GPU → generate proof → verify → submit → claim bounty.
    """
    orchestrator = _get_orchestrator()
    executor = _get_executor()

    decision = await orchestrator.evaluate_job(req.job)
    if decision is None:
        result = orchestrator._results.get(req.job.id)
        reason = result.error if result else "Unknown"
        return ExecuteResponse(decision=None, result=None, rejected=True, rejection_reason=reason)

    result = await executor.execute(req.job, decision)
    return ExecuteResponse(decision=decision, result=result, rejected=False)


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


@router.get("/jobs/{job_id}/status", response_model=JobResult | None)
async def get_job_status(job_id: str) -> JobResult | None:
    """Get the current status and result of a job."""
    orchestrator = _get_orchestrator()
    return await orchestrator.store.get_result(job_id)


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(job_id: str) -> dict:
    """Cancel a running job and terminate its GPU instance."""
    executor = _get_executor()
    cancelled = await executor.cancel_job(job_id)
    return {"job_id": job_id, "cancelled": cancelled}


@router.get("/jobs/active")
async def list_active_jobs() -> dict:
    """List currently executing jobs and their GPU instances."""
    executor = _get_executor()
    active = executor.get_active_jobs()
    return {
        "count": len(active),
        "jobs": {
            jid: {
                "instance_id": inst.instance_id,
                "provider": inst.provider.value,
                "region": inst.region,
                "gpu_type": inst.gpu_type.value,
                "status": inst.status.value,
            }
            for jid, inst in active.items()
        },
    }


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
        input_size_bytes=2**req.circuit_size,
        bounty_usd=req.bounty_usd,
        bounty_token="USDC",
        bounty_amount=req.bounty_usd,
        deadline=now,
        posted_at=now,
        estimated_gpu_minutes=PROOF_SYSTEM_GPU_MINUTES[ProofSystem.RISC_ZERO]
        * (2 ** (req.circuit_size - 20)),
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
    all_options = await enrich_with_carbon(all_options, get_carbon_source(), get_grid_mapper())

    # Calculate costs
    for opt in all_options:
        gpu_hours = job.estimated_gpu_minutes / 60.0
        opt.estimated_job_cost_usd = round(opt.cost_per_gpu_hour_usd * gpu_hours * opt.gpu_count, 4)

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


@router.get("/metrics")
async def broker_metrics_endpoint() -> dict:
    """Get detailed broker metrics (job throughput, revenue, carbon, performance)."""
    return broker_metrics.get_summary()


@router.get("/events", response_model=list[JobEvent])
async def broker_events(limit: int = 100) -> list[JobEvent]:
    """Get recent job lifecycle events for the activity feed."""
    return broker_metrics.get_recent_events(limit)


@router.get("/policy", response_model=CarbonPolicy)
async def get_policy() -> CarbonPolicy:
    """Get current carbon routing policy."""
    return _get_orchestrator().policy


@router.put("/policy", response_model=CarbonPolicy)
async def update_policy(policy: CarbonPolicy) -> CarbonPolicy:
    """Update carbon routing policy (applies to both orchestrator and executor)."""
    orchestrator = _get_orchestrator()
    orchestrator.policy = policy
    # Sync policy to executor so pre-dispatch re-validation uses new thresholds
    executor = _get_executor()
    executor.policy = policy
    logger.info(
        "Carbon policy updated: max_intensity=%s gCO2/kWh, min_renewable=%s%%, btm_required=%s",
        policy.max_carbon_intensity_gco2_kwh,
        policy.min_renewable_percentage,
        policy.require_behind_the_meter,
    )
    return policy


@router.get("/compute/available", response_model=list[ComputeOption])
async def list_compute(min_vram_gb: int = 0) -> list[ComputeOption]:
    """List all available GPU compute options with live carbon data."""
    from carbon_mesh.zk.compute_providers import MockGPUProvider, enrich_with_carbon

    options = await MockGPUProvider().list_available(min_vram_gb=min_vram_gb)
    return await enrich_with_carbon(options, get_carbon_source(), get_grid_mapper())


@router.get("/compute/spot-prices", response_model=list[SpotPriceQuote])
async def list_spot_prices() -> list[SpotPriceQuote]:
    """Get live GPU spot prices from all providers."""
    feed = _get_spot_feed()
    return await feed.get_prices()


@router.get("/runtime/networks")
async def list_prover_networks() -> list[dict]:
    """List supported prover networks with their Docker images and configs."""
    from carbon_mesh.zk.prover_runtime import ProverRuntime

    runtime = ProverRuntime()
    return runtime.list_supported_networks()


@router.get("/runtime/verifiers")
async def check_verifiers() -> dict:
    """Check which proof verifiers are available on this system."""
    from carbon_mesh.zk.verification import ProofVerifier

    verifier = ProofVerifier()
    return await verifier.check_verifiers()


@router.get("/wallet", response_model=WalletInfo)
async def get_wallet_info() -> WalletInfo:
    """Get broker wallet address and balance."""
    wallet = _get_wallet()
    return await wallet.get_info()


@router.get("/wallet/transactions")
async def get_wallet_transactions() -> list[dict]:
    """Get recent wallet transactions (proof submissions and bounty claims)."""
    wallet = _get_wallet()
    return [tx.model_dump() for tx in wallet.get_transaction_log()]


@router.get("/poller/status")
async def poller_status() -> dict:
    """Get the background job poller status."""
    global _poller
    if _poller is None:
        return {
            "running": False,
            "message": "Poller not started. Set CARBON_MESH_ZK_EXECUTOR_ENABLED=true.",
        }
    return _poller.get_status()


@router.post("/poller/start")
async def start_poller() -> dict:
    """Start the background job poller."""
    global _poller
    if _poller is None:
        from carbon_mesh.zk.poller import JobPoller

        _poller = JobPoller(
            orchestrator=_get_orchestrator(),
            executor=_get_executor(),
            auto_execute=False,  # Evaluate-only by default; set True for autopilot
        )
    await _poller.start()
    return _poller.get_status()


@router.post("/poller/stop")
async def stop_poller() -> dict:
    """Stop the background job poller."""
    global _poller
    if _poller is None:
        return {"running": False}
    await _poller.stop()
    return _poller.get_status()
