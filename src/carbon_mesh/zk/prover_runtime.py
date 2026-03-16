"""Prover runtime abstraction — maps proof jobs to Docker container executions.

Each prover network has its own Docker image, CLI interface, and I/O format.
This module provides a unified interface for:
  1. Selecting the correct Docker image for a job
  2. Preparing witness data in the format the prover expects
  3. Parsing proof output from the container
  4. Estimating resource requirements (VRAM, disk, time)

The actual container execution is delegated to the GPU lifecycle manager.
"""

from __future__ import annotations

import logging
import struct

from carbon_mesh.models.zk import (
    PROOF_SYSTEM_GPU_MINUTES,
    PROVER_IMAGES,
    ProofJob,
    ProofSystem,
    ProverDockerImage,
    ProverNetwork,
)

logger = logging.getLogger(__name__)


class ProverRuntime:
    """Maps proof jobs to their Docker container configuration."""

    def __init__(self, image_overrides: dict[ProverNetwork, ProverDockerImage] | None = None) -> None:
        self._images = dict(PROVER_IMAGES)
        if image_overrides:
            self._images.update(image_overrides)

    def get_image(self, network: ProverNetwork) -> ProverDockerImage:
        """Get the Docker image config for a prover network."""
        image = self._images.get(network)
        if not image:
            raise ValueError(f"No prover image configured for network: {network.value}")
        return image

    def get_image_for_job(self, job: ProofJob) -> ProverDockerImage:
        """Get the Docker image config for a specific job, with job-specific overrides."""
        image = self.get_image(job.network)

        # Adjust VRAM requirement based on circuit size
        adjusted_vram = self._estimate_vram(job)
        if adjusted_vram > image.min_vram_gb:
            image = image.model_copy(update={"min_vram_gb": adjusted_vram})

        return image

    def prepare_witness_data(self, job: ProofJob, raw_witness: bytes) -> bytes:
        """Prepare witness data in the format expected by the prover.

        Different proof systems expect different input formats:
        - RISC Zero / SP1: Raw ELF + input bytes
        - HALO2 / PLONK: Serialized circuit + witness
        - STARK: Execution trace
        - Groth16: R1CS witness
        """
        # Prepend a simple header with job metadata
        header = struct.pack(
            "<4sII",
            b"ZKWT",  # Magic bytes
            job.circuit_size,
            len(raw_witness),
        )
        return header + raw_witness

    def parse_proof_output(self, proof_data: bytes) -> dict:
        """Parse proof output and extract metadata.

        Returns a dict with proof metadata (system-specific).
        """
        if not proof_data:
            return {"valid": False, "error": "empty proof data"}

        return {
            "valid": True,
            "size_bytes": len(proof_data),
            "hash_prefix": proof_data[:32].hex() if len(proof_data) >= 32 else proof_data.hex(),
        }

    def estimate_gpu_minutes(self, job: ProofJob) -> float:
        """Estimate GPU time for a proof job based on proof system and circuit size.

        Uses base estimates from PROOF_SYSTEM_GPU_MINUTES, scaled by circuit size.
        Circuit size is log2 of constraint count: a size-22 circuit has 4x
        the constraints of a size-20 circuit.
        """
        base = PROOF_SYSTEM_GPU_MINUTES.get(job.proof_system, 3.0)
        # Scale by circuit size relative to base (2^20)
        scale_factor = 2.0 ** max(0, job.circuit_size - 20)
        return base * scale_factor

    def list_supported_networks(self) -> list[dict]:
        """List all configured prover networks with their Docker images."""
        return [
            {
                "network": net.value,
                "proof_system": img.proof_system.value,
                "image": img.image,
                "gpu_required": img.gpu_required,
                "min_vram_gb": img.min_vram_gb,
            }
            for net, img in self._images.items()
        ]

    @staticmethod
    def _estimate_vram(job: ProofJob) -> int:
        """Estimate VRAM requirement based on circuit size and proof system.

        Larger circuits need more VRAM for the polynomial commitments
        and FFT buffers. This is a conservative estimate.
        """
        base_vram = {
            ProofSystem.GROTH16: 8,
            ProofSystem.PLONK: 12,
            ProofSystem.STARK: 16,
            ProofSystem.HALO2: 16,
            ProofSystem.SP1: 12,
            ProofSystem.RISC_ZERO: 12,
            ProofSystem.NOVA: 8,
        }
        base = base_vram.get(job.proof_system, 16)

        # Each doubling of circuit size roughly doubles VRAM need
        if job.circuit_size > 20:
            base = base * (2 ** (job.circuit_size - 20))

        # Cap at 80 GB (A100 80GB max)
        return min(base, 80)
