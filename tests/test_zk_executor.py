"""Tests for the ZK broker execution pipeline — persistence, GPU lifecycle,
prover runtime, verification, wallet, spot prices, executor, and monitoring."""

import pytest
from datetime import datetime, timedelta, timezone

from carbon_mesh.models.zk import (
    CarbonPolicy,
    ComputeOption,
    ComputeProvider,
    DispatchDecision,
    GPUInstance,
    GPUType,
    GPU_TDP_WATTS,
    InstanceStatus,
    JobResult,
    JobStatus,
    ProofArtifact,
    ProofJob,
    ProofSystem,
    ProverDockerImage,
    ProverNetwork,
    PROOF_SYSTEM_GPU_MINUTES,
    PROVER_IMAGES,
    SpotPriceQuote,
    TransactionReceipt,
    VerificationResult,
    WalletInfo,
)


# --- Helpers ---


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


def _make_decision(job: ProofJob) -> DispatchDecision:
    return DispatchDecision(
        job_id=job.id,
        chosen_provider=ComputeOption(
            provider=ComputeProvider.HIVE_DIGITAL,
            region="is-reykjavik",
            gpu_type=GPUType.A100_40GB,
            gpu_count=1,
            vram_gb=40,
            cost_per_gpu_hour_usd=0.90,
            estimated_job_cost_usd=0.045,
            grid_zone="IS",
            carbon_intensity_gco2_kwh=0.0,
            renewable_percentage=100.0,
            is_behind_the_meter=True,
            available=True,
            estimated_startup_seconds=15,
        ),
        carbon_score=0.0,
        cost_score=0.009,
        combined_score=0.0036,
        estimated_profit_usd=4.955,
        profit_margin_pct=99.1,
        carbon_grams_co2=0.0,
        carbon_saved_vs_grid_avg_grams=0.01,
        dispatched_at=datetime.now(timezone.utc),
    )


# --- Persistence tests ---


@pytest.mark.asyncio
async def test_in_memory_store_save_and_get_job():
    from carbon_mesh.zk.persistence import InMemoryJobStore

    store = InMemoryJobStore()
    job = _make_job()
    await store.save_job(job)

    retrieved = await store.get_job(job.id)
    assert retrieved is not None
    assert retrieved.id == job.id
    assert retrieved.bounty_usd == job.bounty_usd


@pytest.mark.asyncio
async def test_in_memory_store_save_and_get_result():
    from carbon_mesh.zk.persistence import InMemoryJobStore

    store = InMemoryJobStore()
    result = JobResult(job_id="test-123", status=JobStatus.COMPLETED, bounty_earned_usd=5.0)
    await store.save_result(result)

    retrieved = await store.get_result("test-123")
    assert retrieved is not None
    assert retrieved.status == JobStatus.COMPLETED


@pytest.mark.asyncio
async def test_in_memory_store_update_status():
    from carbon_mesh.zk.persistence import InMemoryJobStore

    store = InMemoryJobStore()
    result = JobResult(job_id="test-456", status=JobStatus.PENDING)
    await store.save_result(result)
    await store.update_status("test-456", JobStatus.PROVING)

    retrieved = await store.get_result("test-456")
    assert retrieved is not None
    assert retrieved.status == JobStatus.PROVING


@pytest.mark.asyncio
async def test_in_memory_store_count_by_status():
    from carbon_mesh.zk.persistence import InMemoryJobStore

    store = InMemoryJobStore()
    await store.save_result(JobResult(job_id="a", status=JobStatus.COMPLETED))
    await store.save_result(JobResult(job_id="b", status=JobStatus.COMPLETED))
    await store.save_result(JobResult(job_id="c", status=JobStatus.FAILED))

    counts = await store.count_by_status()
    assert counts["completed"] == 2
    assert counts["failed"] == 1


# --- Prover runtime tests ---


def test_prover_images_cover_all_networks():
    """Every ProverNetwork should have a Docker image configured."""
    for net in ProverNetwork:
        assert net in PROVER_IMAGES, f"Missing prover image for {net.value}"


def test_prover_image_fields():
    """Prover images should have valid image names and proof systems."""
    for net, img in PROVER_IMAGES.items():
        assert img.image, f"Empty image for {net.value}"
        assert "/" in img.image, f"Image should include registry: {img.image}"
        assert img.proof_system in ProofSystem
        assert img.network == net


def test_prover_runtime_get_image():
    from carbon_mesh.zk.prover_runtime import ProverRuntime

    runtime = ProverRuntime()
    img = runtime.get_image(ProverNetwork.BOUNDLESS)
    assert img.proof_system == ProofSystem.RISC_ZERO
    assert "risczero" in img.image.lower() or "risc0" in img.image.lower()


def test_prover_runtime_get_image_for_job():
    from carbon_mesh.zk.prover_runtime import ProverRuntime

    runtime = ProverRuntime()
    job = _make_job(circuit_size=22)
    img = runtime.get_image_for_job(job)
    # Large circuit should increase VRAM requirement
    assert img.min_vram_gb >= 16


def test_prover_runtime_estimate_gpu_minutes():
    from carbon_mesh.zk.prover_runtime import ProverRuntime

    runtime = ProverRuntime()
    job_small = _make_job(circuit_size=20)
    job_large = _make_job(circuit_size=22)

    small_time = runtime.estimate_gpu_minutes(job_small)
    large_time = runtime.estimate_gpu_minutes(job_large)

    # 2^22 has 4x constraints of 2^20, so ~4x GPU time
    assert large_time > small_time
    assert large_time == pytest.approx(small_time * 4, rel=0.1)


def test_prover_runtime_prepare_witness():
    from carbon_mesh.zk.prover_runtime import ProverRuntime

    runtime = ProverRuntime()
    job = _make_job()
    witness = b"\x01\x02\x03"
    prepared = runtime.prepare_witness_data(job, witness)

    # Should have header + witness
    assert len(prepared) > len(witness)
    assert prepared[:4] == b"ZKWT"  # Magic bytes


def test_prover_runtime_list_networks():
    from carbon_mesh.zk.prover_runtime import ProverRuntime

    runtime = ProverRuntime()
    networks = runtime.list_supported_networks()
    assert len(networks) == len(ProverNetwork)
    assert all("network" in n and "image" in n for n in networks)


# --- Spot price feed tests ---


@pytest.mark.asyncio
async def test_spot_prices_returns_quotes():
    from carbon_mesh.zk.spot_prices import SpotPriceFeed

    feed = SpotPriceFeed()
    prices = await feed.get_prices()
    assert len(prices) > 0
    assert all(isinstance(p, SpotPriceQuote) for p in prices)
    # Should be sorted by price
    for i in range(1, len(prices)):
        assert prices[i].price_per_hour_usd >= prices[i - 1].price_per_hour_usd
    await feed.close()


@pytest.mark.asyncio
async def test_spot_prices_filter_by_gpu():
    from carbon_mesh.zk.spot_prices import SpotPriceFeed

    feed = SpotPriceFeed()
    h100_prices = await feed.get_prices(gpu_type=GPUType.H100)
    assert all(p.gpu_type == GPUType.H100 for p in h100_prices)
    await feed.close()


@pytest.mark.asyncio
async def test_spot_prices_green_datacenters_always_available():
    from carbon_mesh.zk.spot_prices import SpotPriceFeed

    feed = SpotPriceFeed()
    prices = await feed.get_prices()
    green_providers = {ComputeProvider.IREN, ComputeProvider.TERAWULF,
                       ComputeProvider.HIVE_DIGITAL, ComputeProvider.BITDEER}
    green_quotes = [p for p in prices if p.provider in green_providers]
    assert len(green_quotes) >= 4  # At least one per green provider
    assert all(p.interruption_rate_pct == 0.0 for p in green_quotes)
    await feed.close()


# --- Wallet tests ---


@pytest.mark.asyncio
async def test_wallet_get_info():
    from carbon_mesh.zk.wallet import LocalWallet

    wallet = LocalWallet(private_key="test_key_123")
    info = await wallet.get_info()
    assert isinstance(info, WalletInfo)
    assert info.address.startswith("0x")
    assert len(info.address) == 42


@pytest.mark.asyncio
async def test_wallet_submit_proof():
    from carbon_mesh.zk.wallet import LocalWallet

    wallet = LocalWallet(private_key="test_key_123")
    receipt = await wallet.submit_proof(
        ProverNetwork.BOUNDLESS, "job-123", b"\x01\x02\x03",
    )
    assert isinstance(receipt, TransactionReceipt)
    assert receipt.tx_hash.startswith("0x")
    assert receipt.status == "built"


@pytest.mark.asyncio
async def test_wallet_claim_bounty():
    from carbon_mesh.zk.wallet import LocalWallet

    wallet = LocalWallet(private_key="test_key_123")
    receipt = await wallet.claim_bounty(
        ProverNetwork.BOUNDLESS, "job-123", "0xabc123",
    )
    assert isinstance(receipt, TransactionReceipt)
    assert receipt.status == "built"


@pytest.mark.asyncio
async def test_wallet_estimate_gas():
    from carbon_mesh.zk.wallet import LocalWallet

    wallet = LocalWallet()
    cost = await wallet.estimate_gas(ProverNetwork.BOUNDLESS, 256)
    assert cost > 0
    # More data = more gas
    cost_large = await wallet.estimate_gas(ProverNetwork.BOUNDLESS, 1024)
    assert cost_large > cost


@pytest.mark.asyncio
async def test_wallet_transaction_log():
    from carbon_mesh.zk.wallet import LocalWallet

    wallet = LocalWallet(private_key="test_key")
    await wallet.submit_proof(ProverNetwork.BOUNDLESS, "j1", b"\x01")
    await wallet.claim_bounty(ProverNetwork.BOUNDLESS, "j1", "0xabc")

    log = wallet.get_transaction_log()
    assert len(log) == 2


# --- Verification tests ---


@pytest.mark.asyncio
async def test_verification_empty_proof():
    from carbon_mesh.zk.verification import ProofVerifier

    verifier = ProofVerifier(prefer_native=False, docker_fallback=False)
    artifact = ProofArtifact(
        job_id="test-1",
        network=ProverNetwork.BOUNDLESS,
        proof_system=ProofSystem.RISC_ZERO,
        proof_data=b"",
    )
    result = await verifier.verify(artifact)
    assert not result.valid
    assert "No proof data" in result.error


@pytest.mark.asyncio
async def test_verification_structural_valid():
    from carbon_mesh.zk.verification import ProofVerifier
    import hashlib

    verifier = ProofVerifier(prefer_native=False, docker_fallback=False)
    proof_data = b"\x01" * 256  # Valid size for RISC_ZERO
    artifact = ProofArtifact(
        job_id="test-2",
        network=ProverNetwork.BOUNDLESS,
        proof_system=ProofSystem.RISC_ZERO,
        proof_data=proof_data,
        proof_hash=hashlib.sha256(proof_data).hexdigest(),
    )
    result = await verifier.verify(artifact)
    assert result.valid
    assert result.verifier == "structural"


@pytest.mark.asyncio
async def test_verification_structural_too_small():
    from carbon_mesh.zk.verification import ProofVerifier

    verifier = ProofVerifier(prefer_native=False, docker_fallback=False)
    artifact = ProofArtifact(
        job_id="test-3",
        network=ProverNetwork.BOUNDLESS,
        proof_system=ProofSystem.RISC_ZERO,
        proof_data=b"\x01\x02",  # Way too small
        proof_hash="",
    )
    result = await verifier.verify(artifact)
    assert not result.valid
    assert "too small" in result.error.lower()


@pytest.mark.asyncio
async def test_verification_all_zeros():
    from carbon_mesh.zk.verification import ProofVerifier

    verifier = ProofVerifier(prefer_native=False, docker_fallback=False)
    artifact = ProofArtifact(
        job_id="test-4",
        network=ProverNetwork.BOUNDLESS,
        proof_system=ProofSystem.RISC_ZERO,
        proof_data=b"\x00" * 256,
    )
    result = await verifier.verify(artifact)
    assert not result.valid
    assert "zeros" in result.error.lower()


@pytest.mark.asyncio
async def test_verification_hash_mismatch():
    from carbon_mesh.zk.verification import ProofVerifier

    verifier = ProofVerifier(prefer_native=False, docker_fallback=False)
    artifact = ProofArtifact(
        job_id="test-5",
        network=ProverNetwork.BOUNDLESS,
        proof_system=ProofSystem.RISC_ZERO,
        proof_data=b"\x01" * 256,
        proof_hash="badhash",
    )
    result = await verifier.verify(artifact)
    assert not result.valid
    assert "mismatch" in result.error.lower()


# --- Monitoring tests ---


def test_metrics_record_job_lifecycle():
    from carbon_mesh.zk.monitoring import BrokerMetrics

    metrics = BrokerMetrics()
    job = _make_job()
    decision = _make_decision(job)

    metrics.record_job_received(job)
    assert metrics.jobs_received == 1
    assert metrics.jobs_by_network["boundless"] == 1

    metrics.record_dispatch(job, decision)
    assert metrics.jobs_dispatched == 1

    result = JobResult(
        job_id=job.id,
        status=JobStatus.COMPLETED,
        compute_cost_usd=0.045,
        bounty_earned_usd=5.0,
        profit_usd=4.955,
        carbon_grams_co2=0.0,
    )
    metrics.record_job_completed(result)
    assert metrics.jobs_completed == 1
    assert metrics.total_profit_usd == pytest.approx(4.955)


def test_metrics_summary():
    from carbon_mesh.zk.monitoring import BrokerMetrics

    metrics = BrokerMetrics()
    job = _make_job()
    decision = _make_decision(job)
    metrics.record_job_received(job)
    metrics.record_dispatch(job, decision)

    artifact = ProofArtifact(
        job_id=job.id,
        network=ProverNetwork.BOUNDLESS,
        proof_system=ProofSystem.RISC_ZERO,
        generation_gpu_seconds=120.0,
        proof_size_bytes=256,
    )
    metrics.record_proof_generated(artifact)

    summary = metrics.get_summary()
    assert summary["jobs"]["received"] == 1
    assert summary["jobs"]["dispatched"] == 1
    assert summary["performance"]["avg_proving_seconds"] == pytest.approx(120.0)


def test_metrics_events():
    from carbon_mesh.zk.monitoring import BrokerMetrics

    metrics = BrokerMetrics()
    job = _make_job()
    metrics.record_job_received(job)

    events = metrics.get_recent_events()
    assert len(events) == 1
    assert events[0].event_type == "job_received"
    assert events[0].details["network"] == "boundless"


# --- GPU lifecycle tests ---


@pytest.mark.asyncio
async def test_local_docker_provision():
    from carbon_mesh.zk.gpu_lifecycle import LocalDockerBackend

    backend = LocalDockerBackend()
    option = ComputeOption(
        provider=ComputeProvider.HIVE_DIGITAL,
        region="is-reykjavik",
        gpu_type=GPUType.A100_40GB,
        gpu_count=1,
        vram_gb=40,
        cost_per_gpu_hour_usd=0.90,
        estimated_job_cost_usd=0.0,
        grid_zone="IS",
        carbon_intensity_gco2_kwh=0.0,
        renewable_percentage=100.0,
        is_behind_the_meter=True,
    )

    instance = await backend.provision(option, "test-job-1")
    assert isinstance(instance, GPUInstance)
    assert instance.status == InstanceStatus.RUNNING
    assert instance.ip_address == "127.0.0.1"
    assert instance.job_id == "test-job-1"


@pytest.mark.asyncio
async def test_local_docker_wait_ready():
    from carbon_mesh.zk.gpu_lifecycle import LocalDockerBackend

    backend = LocalDockerBackend()
    instance = GPUInstance(
        instance_id="local-test",
        provider=ComputeProvider.HIVE_DIGITAL,
        region="local",
        gpu_type=GPUType.A100_40GB,
        gpu_count=1,
        vram_gb=40,
        status=InstanceStatus.PENDING,
    )
    ready = await backend.wait_ready(instance)
    assert ready.status == InstanceStatus.RUNNING


@pytest.mark.asyncio
async def test_local_docker_terminate():
    from carbon_mesh.zk.gpu_lifecycle import LocalDockerBackend

    backend = LocalDockerBackend()
    instance = GPUInstance(
        instance_id="local-test",
        provider=ComputeProvider.HIVE_DIGITAL,
        region="local",
        gpu_type=GPUType.A100_40GB,
        gpu_count=1,
        vram_gb=40,
        status=InstanceStatus.RUNNING,
        job_id="test-1",
    )
    await backend.terminate(instance)
    assert instance.status == InstanceStatus.TERMINATED


# --- Executor tests ---


@pytest.mark.asyncio
async def test_executor_handles_failure_gracefully():
    """Executor should return FAILED result when prover produces no output."""
    from carbon_mesh.zk.executor import JobExecutor
    from carbon_mesh.zk.gpu_lifecycle import LocalDockerBackend
    from carbon_mesh.zk.monitoring import BrokerMetrics
    from carbon_mesh.zk.persistence import InMemoryJobStore

    # The LocalDockerBackend will fail because the prover image doesn't exist locally
    # This tests the error handling path
    store = InMemoryJobStore()
    metrics = BrokerMetrics()
    executor = JobExecutor(
        compute_backend=LocalDockerBackend(),
        store=store,
        metrics=metrics,
    )

    job = _make_job()
    decision = _make_decision(job)
    await store.save_job(job)

    result = await executor.execute(job, decision)
    # Should fail gracefully (no Docker image available)
    assert result.status == JobStatus.FAILED
    assert result.error  # Should have an error message
    assert metrics.jobs_failed == 1


@pytest.mark.asyncio
async def test_executor_cancel_nonexistent_job():
    from carbon_mesh.zk.executor import JobExecutor

    executor = JobExecutor()
    cancelled = await executor.cancel_job("nonexistent-job")
    assert cancelled is False


@pytest.mark.asyncio
async def test_executor_active_jobs_empty():
    from carbon_mesh.zk.executor import JobExecutor

    executor = JobExecutor()
    active = executor.get_active_jobs()
    assert len(active) == 0


# --- Model tests for new types ---


def test_gpu_instance_model():
    instance = GPUInstance(
        instance_id="test-123",
        provider=ComputeProvider.IREN,
        region="ca-bc-1",
        gpu_type=GPUType.RTX_4090,
        vram_gb=24,
    )
    assert instance.status == InstanceStatus.PENDING
    assert instance.ssh_port == 22


def test_spot_price_quote_model():
    quote = SpotPriceQuote(
        provider=ComputeProvider.AWS_SPOT,
        region="us-east-1",
        gpu_type=GPUType.A100_40GB,
        price_per_hour_usd=1.10,
        fetched_at=datetime.now(timezone.utc),
    )
    assert quote.available is True
    assert quote.interruption_rate_pct == 0.0


def test_proof_artifact_model():
    artifact = ProofArtifact(
        job_id="test-1",
        network=ProverNetwork.BOUNDLESS,
        proof_system=ProofSystem.RISC_ZERO,
        proof_data=b"\x01" * 128,
        proof_hash="abc123",
        proof_size_bytes=128,
    )
    assert artifact.generation_gpu_seconds == 0


def test_verification_result_model():
    result = VerificationResult(
        job_id="test-1",
        valid=True,
        verifier="structural",
        verification_time_ms=1.5,
    )
    assert result.error == ""


def test_wallet_info_model():
    info = WalletInfo(address="0x" + "a" * 40)
    assert info.chain_id == 1
    assert info.balance_eth == 0.0


def test_transaction_receipt_model():
    receipt = TransactionReceipt(tx_hash="0x" + "b" * 64)
    assert receipt.status == "pending"
    assert receipt.block_number == 0
