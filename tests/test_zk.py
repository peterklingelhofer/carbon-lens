"""Tests for the ZK broker — orchestrator, compute providers, prover networks."""

import pytest
from datetime import datetime, timedelta, timezone

from carbon_mesh.models.zk import (
    CarbonPolicy,
    ComputeOption,
    GPUType,
    GPU_TDP_WATTS,
    JobStatus,
    ProofJob,
    ProofSystem,
    ProverNetwork,
    PROOF_SYSTEM_GPU_MINUTES,
)
from carbon_mesh.zk.compute_providers import MockGPUProvider
from carbon_mesh.zk.prover_networks import MockProverNetwork
from carbon_mesh.zk.orchestrator import JobOrchestrator
from carbon_mesh.carbon_sources.mock import MockCarbonSource
from carbon_mesh.grid.mapper import GridMapper
from carbon_mesh.config import settings


# --- Fixtures ---


def _make_job(
    bounty_usd: float = 5.0,
    circuit_size: int = 20,
    min_vram_gb: int = 16,
    network: ProverNetwork = ProverNetwork.BOUNDLESS,
) -> ProofJob:
    now = datetime.now(timezone.utc)
    return ProofJob(
        id=f"test-{now.timestamp()}",
        network=network,
        proof_system=ProofSystem.RISC_ZERO,
        circuit_size=circuit_size,
        input_size_bytes=2**circuit_size,
        bounty_usd=bounty_usd,
        bounty_token="USDC",
        bounty_amount=bounty_usd,
        deadline=now + timedelta(minutes=15),
        posted_at=now,
        estimated_gpu_minutes=PROOF_SYSTEM_GPU_MINUTES[ProofSystem.RISC_ZERO],
        min_vram_gb=min_vram_gb,
    )


def _make_orchestrator(
    max_carbon: float = 50.0,
    min_renewable: float = 80.0,
    min_margin: float = 10.0,
) -> JobOrchestrator:
    source = MockCarbonSource()
    mapper = GridMapper(settings.region_map_path)
    policy = CarbonPolicy(
        max_carbon_intensity_gco2_kwh=max_carbon,
        min_renewable_percentage=min_renewable,
        min_profit_margin_pct=min_margin,
    )
    return JobOrchestrator(
        carbon_source=source,
        grid_mapper=mapper,
        policy=policy,
    )


# --- Mock GPU Provider tests ---


@pytest.mark.asyncio
async def test_mock_gpu_provider_returns_options():
    provider = MockGPUProvider()
    options = await provider.list_available()
    assert len(options) > 0
    assert all(isinstance(o, ComputeOption) for o in options)


@pytest.mark.asyncio
async def test_mock_gpu_provider_filters_by_vram():
    provider = MockGPUProvider()
    all_options = await provider.list_available()
    filtered = await provider.list_available(min_vram_gb=40)
    assert len(filtered) < len(all_options)
    assert all(o.vram_gb >= 40 for o in filtered)


@pytest.mark.asyncio
async def test_mock_gpu_provider_has_green_options():
    provider = MockGPUProvider()
    options = await provider.list_available()
    green = [o for o in options if o.is_behind_the_meter]
    assert len(green) >= 4  # IREN, TeraWulf, Hive Digital x2, Bitdeer


# --- Prover Network tests ---


@pytest.mark.asyncio
async def test_mock_prover_boundless():
    adapter = MockProverNetwork(ProverNetwork.BOUNDLESS)
    jobs = await adapter.fetch_available_jobs()
    assert len(jobs) == 2
    assert all(j.network == ProverNetwork.BOUNDLESS for j in jobs)
    assert all(j.bounty_usd > 0 for j in jobs)


@pytest.mark.asyncio
async def test_mock_prover_scroll():
    adapter = MockProverNetwork(ProverNetwork.SCROLL)
    jobs = await adapter.fetch_available_jobs()
    assert len(jobs) == 1
    assert jobs[0].proof_system == ProofSystem.HALO2


@pytest.mark.asyncio
async def test_mock_prover_unknown_network():
    adapter = MockProverNetwork(ProverNetwork.ZKSYNC)
    jobs = await adapter.fetch_available_jobs()
    assert jobs == []


# --- Orchestrator tests ---


@pytest.mark.asyncio
async def test_orchestrator_evaluates_profitable_job():
    orch = _make_orchestrator(max_carbon=500, min_renewable=0, min_margin=5)
    job = _make_job(bounty_usd=10.0)
    decision = await orch.evaluate_job(job)

    assert decision is not None
    assert decision.estimated_profit_usd > 0
    assert decision.profit_margin_pct > 0
    assert decision.chosen_provider.available


@pytest.mark.asyncio
async def test_orchestrator_rejects_unprofitable_job():
    orch = _make_orchestrator(max_carbon=500, min_renewable=0, min_margin=99)
    job = _make_job(bounty_usd=0.01)  # Tiny bounty
    decision = await orch.evaluate_job(job)

    assert decision is None
    result = orch._results.get(job.id)
    assert result is not None
    assert result.status == JobStatus.REJECTED


@pytest.mark.asyncio
async def test_orchestrator_strict_carbon_policy():
    """With max_carbon=0 and min_renewable=100, only behind-the-meter zero-carbon options pass."""
    orch = _make_orchestrator(max_carbon=0, min_renewable=100, min_margin=0)
    job = _make_job(bounty_usd=100.0)  # High bounty to ensure profitability
    decision = await orch.evaluate_job(job)

    # Iceland (Hive Digital) has 0 gCO2/kWh and 100% renewable
    if decision is not None:
        assert decision.chosen_provider.carbon_intensity_gco2_kwh == 0
        assert decision.chosen_provider.renewable_percentage == 100
        assert decision.chosen_provider.is_behind_the_meter


@pytest.mark.asyncio
async def test_orchestrator_prefers_behind_the_meter():
    orch = _make_orchestrator(max_carbon=500, min_renewable=0, min_margin=0)
    orch.policy = orch.policy.model_copy(update={"prefer_behind_the_meter": True})
    job = _make_job(bounty_usd=50.0)
    decision = await orch.evaluate_job(job)

    assert decision is not None
    # With BTM preference and enough bounty, should pick a green center
    assert decision.chosen_provider.is_behind_the_meter


@pytest.mark.asyncio
async def test_orchestrator_complete_job():
    orch = _make_orchestrator(max_carbon=500, min_renewable=0, min_margin=0)
    job = _make_job(bounty_usd=10.0)
    await orch.evaluate_job(job)

    result = await orch.complete_job(job.id, success=True, gpu_seconds=120)
    assert result.status == JobStatus.COMPLETED
    assert result.bounty_earned_usd == 10.0
    assert result.compute_cost_usd > 0
    assert result.profit_usd > 0


@pytest.mark.asyncio
async def test_orchestrator_stats_after_jobs():
    orch = _make_orchestrator(max_carbon=500, min_renewable=0, min_margin=0)

    # Run a couple jobs
    job1 = _make_job(bounty_usd=5.0)
    job2 = _make_job(bounty_usd=8.0)
    await orch.evaluate_job(job1)
    await orch.evaluate_job(job2)
    await orch.complete_job(job1.id, success=True, gpu_seconds=60)
    await orch.complete_job(job2.id, success=True, gpu_seconds=90)

    stats = orch.get_stats()
    assert stats.completed_jobs == 2
    assert stats.total_bounties_earned_usd == 13.0
    assert stats.total_profit_usd > 0
    assert stats.avg_profit_margin_pct > 0


# --- GPU TDP and proof system constants ---


def test_gpu_tdp_values():
    assert GPU_TDP_WATTS[GPUType.H100] == 700
    assert GPU_TDP_WATTS[GPUType.T4] == 70
    assert GPU_TDP_WATTS[GPUType.RTX_4090] == 450


def test_proof_system_estimates():
    assert (
        PROOF_SYSTEM_GPU_MINUTES[ProofSystem.GROTH16] < PROOF_SYSTEM_GPU_MINUTES[ProofSystem.STARK]
    )
    assert all(v > 0 for v in PROOF_SYSTEM_GPU_MINUTES.values())


# --- Carbon policy ---


def test_carbon_policy_defaults():
    policy = CarbonPolicy()
    assert policy.max_carbon_intensity_gco2_kwh == 10.0  # Near-zero default
    assert policy.min_renewable_percentage == 95.0  # 95%+ renewable
    assert policy.require_behind_the_meter is True  # BTM only
    assert policy.carbon_weight + policy.cost_weight == 1.0


def test_carbon_policy_zero_carbon():
    policy = CarbonPolicy(
        max_carbon_intensity_gco2_kwh=0,
        min_renewable_percentage=100,
    )
    assert policy.max_carbon_intensity_gco2_kwh == 0
