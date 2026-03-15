"""Prover network integration — connects to decentralized ZK proof marketplaces.

Each adapter polls a prover network for available proof jobs (bounties).
The broker evaluates profitability and dispatches to green compute.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Protocol, runtime_checkable

from carbon_mesh.models.zk import (
    ProofJob,
    ProofSystem,
    ProverNetwork,
    PROOF_SYSTEM_GPU_MINUTES,
)

logger = logging.getLogger(__name__)


@runtime_checkable
class ProverNetworkAdapter(Protocol):
    """Protocol for prover network integrations."""

    network: ProverNetwork

    async def fetch_available_jobs(self) -> list[ProofJob]:
        """Poll the network for available proof jobs."""
        ...

    async def submit_proof(self, job_id: str, proof_data: bytes) -> str:
        """Submit a generated proof. Returns transaction hash."""
        ...

    async def claim_bounty(self, job_id: str, tx_hash: str) -> float:
        """Claim the bounty for a completed proof. Returns USD value."""
        ...


class MockProverNetwork:
    """Mock prover network that generates realistic job listings for demo."""

    network = ProverNetwork.BOUNDLESS

    def __init__(self, network: ProverNetwork = ProverNetwork.BOUNDLESS) -> None:
        self.network = network

    async def fetch_available_jobs(self) -> list[ProofJob]:
        now = datetime.now(timezone.utc)
        deadline = now + timedelta(minutes=15)

        # Realistic job mix from different proof systems
        jobs = {
            ProverNetwork.BOUNDLESS: [
                ProofJob(
                    id=f"bndl-{uuid.uuid4().hex[:8]}",
                    network=ProverNetwork.BOUNDLESS,
                    proof_system=ProofSystem.RISC_ZERO,
                    circuit_size=20,
                    input_size_bytes=32_768,
                    bounty_usd=2.50,
                    bounty_token="ETH",
                    bounty_amount=0.001,
                    deadline=deadline,
                    posted_at=now,
                    estimated_gpu_minutes=PROOF_SYSTEM_GPU_MINUTES[ProofSystem.RISC_ZERO] * 1.0,
                    min_vram_gb=16,
                ),
                ProofJob(
                    id=f"bndl-{uuid.uuid4().hex[:8]}",
                    network=ProverNetwork.BOUNDLESS,
                    proof_system=ProofSystem.RISC_ZERO,
                    circuit_size=22,
                    input_size_bytes=131_072,
                    bounty_usd=8.00,
                    bounty_token="ETH",
                    bounty_amount=0.0032,
                    deadline=deadline + timedelta(minutes=10),
                    posted_at=now,
                    estimated_gpu_minutes=PROOF_SYSTEM_GPU_MINUTES[ProofSystem.RISC_ZERO] * 4.0,
                    min_vram_gb=24,
                ),
            ],
            ProverNetwork.SUCCINCT: [
                ProofJob(
                    id=f"sp1-{uuid.uuid4().hex[:8]}",
                    network=ProverNetwork.SUCCINCT,
                    proof_system=ProofSystem.SP1,
                    circuit_size=21,
                    input_size_bytes=65_536,
                    bounty_usd=3.75,
                    bounty_token="USDC",
                    bounty_amount=3.75,
                    deadline=deadline,
                    posted_at=now,
                    estimated_gpu_minutes=PROOF_SYSTEM_GPU_MINUTES[ProofSystem.SP1] * 2.0,
                    min_vram_gb=16,
                ),
            ],
            ProverNetwork.SCROLL: [
                ProofJob(
                    id=f"scrl-{uuid.uuid4().hex[:8]}",
                    network=ProverNetwork.SCROLL,
                    proof_system=ProofSystem.HALO2,
                    circuit_size=23,
                    input_size_bytes=262_144,
                    bounty_usd=15.00,
                    bounty_token="ETH",
                    bounty_amount=0.006,
                    deadline=deadline + timedelta(minutes=20),
                    posted_at=now,
                    estimated_gpu_minutes=PROOF_SYSTEM_GPU_MINUTES[ProofSystem.HALO2] * 8.0,
                    min_vram_gb=40,
                ),
            ],
            ProverNetwork.ALEO: [
                ProofJob(
                    id=f"aleo-{uuid.uuid4().hex[:8]}",
                    network=ProverNetwork.ALEO,
                    proof_system=ProofSystem.GROTH16,
                    circuit_size=20,
                    input_size_bytes=16_384,
                    bounty_usd=1.80,
                    bounty_token="ALEO",
                    bounty_amount=5.0,
                    deadline=deadline,
                    posted_at=now,
                    estimated_gpu_minutes=PROOF_SYSTEM_GPU_MINUTES[ProofSystem.GROTH16] * 1.0,
                    min_vram_gb=8,
                ),
            ],
            ProverNetwork.GEVULOT: [
                ProofJob(
                    id=f"gvlt-{uuid.uuid4().hex[:8]}",
                    network=ProverNetwork.GEVULOT,
                    proof_system=ProofSystem.STARK,
                    circuit_size=22,
                    input_size_bytes=524_288,
                    bounty_usd=12.00,
                    bounty_token="USDC",
                    bounty_amount=12.00,
                    deadline=deadline + timedelta(minutes=15),
                    posted_at=now,
                    estimated_gpu_minutes=PROOF_SYSTEM_GPU_MINUTES[ProofSystem.STARK] * 4.0,
                    min_vram_gb=24,
                ),
            ],
        }

        return jobs.get(self.network, [])

    async def submit_proof(self, job_id: str, proof_data: bytes) -> str:
        """Mock proof submission — returns a fake tx hash."""
        return f"0x{uuid.uuid4().hex}"

    async def claim_bounty(self, job_id: str, tx_hash: str) -> float:
        """Mock bounty claim — returns a fixed amount."""
        return 2.50  # USD
