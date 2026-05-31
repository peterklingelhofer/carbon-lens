"""Local proof verification — validate proofs before on-chain submission.

Pre-verifying proofs locally prevents:
  1. Gas waste from submitting invalid proofs
  2. Slashing penalties on networks with staking requirements
  3. Reputation damage from failed submissions

Each proof system has a lightweight verifier that can check proof validity
without the full prover stack. These verifiers are typically:
  - Rust binaries (risc0-verifier, sp1-verifier)
  - Docker containers (for verifiers that need specific dependencies)
  - Native libraries called via subprocess

This module wraps verifier invocations and returns structured results.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import tempfile
import time

from carbon_mesh.models.zk import (
    ProofArtifact,
    ProofSystem,
    VerificationResult,
)

logger = logging.getLogger(__name__)


# Verifier Docker images — lightweight containers that just verify (no GPU needed)
VERIFIER_IMAGES: dict[ProofSystem, str] = {
    ProofSystem.RISC_ZERO: "risczero/risc0-verifier:1.2",
    ProofSystem.SP1: "succinctlabs/sp1-verifier:latest",
    ProofSystem.HALO2: "scrolltech/scroll-verifier:latest",
    ProofSystem.GROTH16: "gnark/groth16-verifier:latest",
    ProofSystem.STARK: "starkware/stone-verifier:latest",
    ProofSystem.PLONK: "gnark/plonk-verifier:latest",
    ProofSystem.NOVA: "microsoft/nova-verifier:latest",
}

# Native verifier binary names (if installed locally)
VERIFIER_BINARIES: dict[ProofSystem, str] = {
    ProofSystem.RISC_ZERO: "risc0-verifier",
    ProofSystem.SP1: "sp1-verifier",
    ProofSystem.HALO2: "halo2-verifier",
    ProofSystem.GROTH16: "gnark-verifier",
    ProofSystem.STARK: "cpu_air_verifier",
    ProofSystem.PLONK: "gnark-verifier",
    ProofSystem.NOVA: "nova-verifier",
}


class ProofVerifier:
    """Verifies ZK proofs locally before on-chain submission."""

    def __init__(self, prefer_native: bool = True, docker_fallback: bool = True) -> None:
        self._prefer_native = prefer_native
        self._docker_fallback = docker_fallback
        self._native_available: dict[ProofSystem, bool] = {}

    async def verify(self, artifact: ProofArtifact) -> VerificationResult:
        """Verify a proof artifact.

        Tries native verifier first (if available), falls back to Docker.
        Returns structured verification result.
        """
        from datetime import datetime, timezone

        if not artifact.proof_data:
            return VerificationResult(
                job_id=artifact.job_id,
                valid=False,
                error="No proof data to verify",
                verified_at=datetime.now(timezone.utc),
            )

        # Try native verifier
        if self._prefer_native:
            native_result = await self._verify_native(artifact)
            if native_result is not None:
                return native_result

        # Fall back to Docker verifier
        if self._docker_fallback:
            docker_result = await self._verify_docker(artifact)
            if docker_result is not None:
                return docker_result

        # Last resort: structural validation only
        return self._verify_structural(artifact)

    async def check_verifiers(self) -> dict[str, dict]:
        """Check which verifiers are available on this system."""
        status: dict[str, dict] = {}
        for ps in ProofSystem:
            binary = VERIFIER_BINARIES.get(ps, "")
            native_ok = await self._check_binary(binary) if binary else False
            self._native_available[ps] = native_ok

            docker_image = VERIFIER_IMAGES.get(ps, "")
            docker_ok = await self._check_docker_image(docker_image) if docker_image else False

            status[ps.value] = {
                "native_binary": binary,
                "native_available": native_ok,
                "docker_image": docker_image,
                "docker_available": docker_ok,
                "structural_only": not native_ok and not docker_ok,
            }
        return status

    async def _verify_native(self, artifact: ProofArtifact) -> VerificationResult | None:
        """Verify using a locally installed verifier binary."""
        from datetime import datetime, timezone

        binary = VERIFIER_BINARIES.get(artifact.proof_system)
        if not binary:
            return None

        # Check if binary exists (cache the result)
        if artifact.proof_system not in self._native_available:
            self._native_available[artifact.proof_system] = await self._check_binary(binary)

        if not self._native_available[artifact.proof_system]:
            return None

        start = time.monotonic()

        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(artifact.proof_data)
            proof_path = f.name

        try:
            proc = await asyncio.create_subprocess_exec(
                binary,
                "verify",
                "--proof",
                proof_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            elapsed_ms = (time.monotonic() - start) * 1000

            valid = proc.returncode == 0
            return VerificationResult(
                job_id=artifact.job_id,
                valid=valid,
                verifier=f"native:{binary}",
                verification_time_ms=round(elapsed_ms, 1),
                error="" if valid else stderr.decode()[:500],
                verified_at=datetime.now(timezone.utc),
            )
        except asyncio.TimeoutError:
            return VerificationResult(
                job_id=artifact.job_id,
                valid=False,
                verifier=f"native:{binary}",
                verification_time_ms=60000,
                error="Verification timed out after 60s",
                verified_at=datetime.now(timezone.utc),
            )
        finally:
            os.unlink(proof_path)

    async def _verify_docker(self, artifact: ProofArtifact) -> VerificationResult | None:
        """Verify using a Docker container (no GPU needed for verification)."""
        from datetime import datetime, timezone

        image = VERIFIER_IMAGES.get(artifact.proof_system)
        if not image:
            return None

        start = time.monotonic()

        with tempfile.TemporaryDirectory(prefix="zk-verify-") as tmpdir:
            proof_path = os.path.join(tmpdir, "proof.bin")
            with open(proof_path, "wb") as f:
                f.write(artifact.proof_data)

            cmd = [
                "docker",
                "run",
                "--rm",
                "-v",
                f"{tmpdir}:/data:ro",
                image,
                "verify",
                "--proof",
                "/data/proof.bin",
            ]

            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)
                elapsed_ms = (time.monotonic() - start) * 1000

                valid = proc.returncode == 0
                return VerificationResult(
                    job_id=artifact.job_id,
                    valid=valid,
                    verifier=f"docker:{image}",
                    verification_time_ms=round(elapsed_ms, 1),
                    error="" if valid else stderr.decode()[:500],
                    verified_at=datetime.now(timezone.utc),
                )
            except asyncio.TimeoutError:
                return VerificationResult(
                    job_id=artifact.job_id,
                    valid=False,
                    verifier=f"docker:{image}",
                    verification_time_ms=120000,
                    error="Docker verification timed out after 120s",
                    verified_at=datetime.now(timezone.utc),
                )
            except FileNotFoundError:
                # Docker not installed
                return None

    def _verify_structural(self, artifact: ProofArtifact) -> VerificationResult:
        """Structural validation only — checks proof format, not cryptographic validity.

        This is the last resort when no verifier binary or Docker image is available.
        It checks basic structural properties but cannot verify cryptographic correctness.
        """
        from datetime import datetime, timezone

        start = time.monotonic()
        errors: list[str] = []

        data = artifact.proof_data

        # Check minimum size by proof system
        min_sizes = {
            ProofSystem.GROTH16: 128,  # ~128 bytes (2 G1 + 1 G2 point)
            ProofSystem.PLONK: 256,  # Larger due to polynomial commitments
            ProofSystem.STARK: 1024,  # STARKs are much larger
            ProofSystem.HALO2: 512,  # IPA-based, moderate size
            ProofSystem.SP1: 128,  # Compressed STARK
            ProofSystem.RISC_ZERO: 128,  # Compressed
            ProofSystem.NOVA: 256,  # Folding proof
        }
        min_size = min_sizes.get(artifact.proof_system, 64)
        if len(data) < min_size:
            errors.append(f"Proof too small: {len(data)} bytes < {min_size} minimum")

        # Check for all-zero proofs (definitely invalid)
        if data == b"\x00" * len(data):
            errors.append("Proof is all zeros")

        # Check proof hash matches
        computed_hash = hashlib.sha256(data).hexdigest()
        if artifact.proof_hash and artifact.proof_hash != computed_hash:
            errors.append(
                f"Hash mismatch: expected {artifact.proof_hash[:16]}..., got {computed_hash[:16]}..."
            )

        elapsed_ms = (time.monotonic() - start) * 1000
        valid = len(errors) == 0

        return VerificationResult(
            job_id=artifact.job_id,
            valid=valid,
            verifier="structural",
            verification_time_ms=round(elapsed_ms, 1),
            error="; ".join(errors) if errors else "",
            verified_at=datetime.now(timezone.utc),
        )

    @staticmethod
    async def _check_binary(binary: str) -> bool:
        """Check if a binary is available on PATH."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "which",
                binary,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            return proc.returncode == 0
        except Exception:
            return False

    @staticmethod
    async def _check_docker_image(image: str) -> bool:
        """Check if a Docker image is available locally."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker",
                "image",
                "inspect",
                image,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
            return proc.returncode == 0
        except Exception:
            return False
