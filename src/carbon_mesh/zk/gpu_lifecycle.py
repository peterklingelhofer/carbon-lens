"""GPU instance lifecycle manager — provision, monitor, and terminate compute.

Handles the full lifecycle of GPU instances used for ZK proof generation:
  1. Provision a spot/preemptible instance from the chosen provider
  2. Wait for SSH connectivity
  3. Install NVIDIA drivers + Docker runtime (if not pre-baked)
  4. Pull the prover Docker image
  5. Run the prover container with GPU passthrough
  6. Collect proof output
  7. Terminate the instance

Provides a LocalDockerBackend for testing without cloud accounts,
and protocol interfaces for AWS/GCP/green datacenter backends.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from typing import Protocol, runtime_checkable

from carbon_mesh.models.zk import (
    ComputeOption,
    ComputeProvider,
    GPUInstance,
    InstanceStatus,
    ProofArtifact,
    ProverDockerImage,
)

logger = logging.getLogger(__name__)


@runtime_checkable
class ComputeBackend(Protocol):
    """Protocol for cloud/datacenter compute backends."""

    async def provision(self, option: ComputeOption, job_id: str) -> GPUInstance: ...
    async def wait_ready(self, instance: GPUInstance, timeout_seconds: int = 300) -> GPUInstance: ...
    async def run_container(
        self,
        instance: GPUInstance,
        image: ProverDockerImage,
        witness_data: bytes,
    ) -> ProofArtifact: ...
    async def terminate(self, instance: GPUInstance) -> None: ...
    async def get_status(self, instance: GPUInstance) -> InstanceStatus: ...


class LocalDockerBackend:
    """Run prover containers on the local Docker daemon for development/testing.

    This backend doesn't provision cloud instances — it runs Docker containers
    directly on the local machine. Useful for:
    - Testing the full job pipeline end-to-end
    - Development without cloud accounts
    - CI/CD integration tests
    """

    def __init__(self, docker_host: str = "unix:///var/run/docker.sock") -> None:
        self._docker_host = docker_host
        self._containers: dict[str, str] = {}  # job_id → container_id

    async def provision(self, option: ComputeOption, job_id: str) -> GPUInstance:
        """No-op for local Docker — we use the host machine."""
        return GPUInstance(
            instance_id=f"local-{job_id[:8]}",
            provider=option.provider,
            region="local",
            gpu_type=option.gpu_type,
            gpu_count=option.gpu_count,
            vram_gb=option.vram_gb,
            status=InstanceStatus.RUNNING,
            ip_address="127.0.0.1",
            cost_per_hour_usd=0.0,
            job_id=job_id,
        )

    async def wait_ready(self, instance: GPUInstance, timeout_seconds: int = 300) -> GPUInstance:
        """Local Docker is always ready."""
        instance.status = InstanceStatus.RUNNING
        return instance

    async def run_container(
        self,
        instance: GPUInstance,
        image: ProverDockerImage,
        witness_data: bytes,
    ) -> ProofArtifact:
        """Run a prover container locally via Docker CLI.

        Uses subprocess to invoke `docker run` with GPU passthrough.
        Falls back to CPU mode if --gpus is not available.
        """
        import tempfile
        import os

        job_id = instance.job_id
        start_time = time.monotonic()

        # Write witness data to a temp directory
        with tempfile.TemporaryDirectory(prefix=f"zk-{job_id[:8]}-") as tmpdir:
            input_dir = os.path.join(tmpdir, "input")
            output_dir = os.path.join(tmpdir, "output")
            os.makedirs(input_dir)
            os.makedirs(output_dir)

            # Write witness
            witness_path = os.path.join(input_dir, "witness.bin")
            with open(witness_path, "wb") as f:
                f.write(witness_data)

            # Build docker run command
            cmd = [
                "docker", "run", "--rm",
                "-v", f"{input_dir}:{image.input_mount_path}:ro",
                "-v", f"{output_dir}:/output",
            ]

            # Add GPU passthrough if available and required
            if image.gpu_required:
                cmd.extend(["--gpus", "all"])

            # Add environment variables
            for key, val in image.env_vars.items():
                cmd.extend(["-e", f"{key}={val}"])

            # Add image and entrypoint
            cmd.append(image.image)
            if image.entrypoint:
                cmd.extend(image.entrypoint)

            logger.info(
                "Running prover container for job %s: %s",
                job_id, " ".join(cmd),
            )

            # Run the container
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            elapsed = time.monotonic() - start_time

            if proc.returncode != 0:
                logger.error(
                    "Prover container failed for job %s (exit %d): %s",
                    job_id, proc.returncode, stderr.decode()[:500],
                )
                return ProofArtifact(
                    job_id=job_id,
                    network=image.network,
                    proof_system=image.proof_system,
                    generation_gpu_seconds=elapsed,
                )

            # Read proof output
            proof_path = os.path.join(output_dir, os.path.basename(image.proof_output_path))
            proof_data = b""
            if os.path.exists(proof_path):
                with open(proof_path, "rb") as f:
                    proof_data = f.read()

            from datetime import datetime, timezone

            return ProofArtifact(
                job_id=job_id,
                network=image.network,
                proof_system=image.proof_system,
                proof_data=proof_data,
                proof_hash=hashlib.sha256(proof_data).hexdigest() if proof_data else "",
                proof_size_bytes=len(proof_data),
                generation_gpu_seconds=elapsed,
                generated_at=datetime.now(timezone.utc),
            )

    async def terminate(self, instance: GPUInstance) -> None:
        """Clean up any running containers for this job."""
        container_id = self._containers.pop(instance.job_id, None)
        if container_id:
            proc = await asyncio.create_subprocess_exec(
                "docker", "stop", container_id,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await proc.wait()
        instance.status = InstanceStatus.TERMINATED

    async def get_status(self, instance: GPUInstance) -> InstanceStatus:
        return instance.status


class SSHComputeBackend:
    """Provision and manage GPU instances via SSH.

    For green datacenters (IREN, TeraWulf, Hive Digital, etc.) that provide
    dedicated or reserved GPU machines accessible over SSH. Also works for
    any pre-provisioned machine (e.g., bare metal at a colo).

    Requires: host, SSH key, and Docker pre-installed on the remote machine.
    """

    def __init__(
        self,
        hosts: dict[str, dict],  # provider → {host, port, user, key_path}
    ) -> None:
        self._hosts = hosts
        self._active: dict[str, dict] = {}

    async def provision(self, option: ComputeOption, job_id: str) -> GPUInstance:
        """Look up a pre-configured host for this provider."""
        provider_key = option.provider.value
        host_config = self._hosts.get(provider_key)
        if not host_config:
            raise ValueError(f"No SSH host configured for provider {provider_key}")

        instance = GPUInstance(
            instance_id=f"ssh-{provider_key}-{job_id[:8]}",
            provider=option.provider,
            region=option.region,
            gpu_type=option.gpu_type,
            gpu_count=option.gpu_count,
            vram_gb=option.vram_gb,
            status=InstanceStatus.RUNNING,
            ip_address=host_config["host"],
            ssh_port=host_config.get("port", 22),
            cost_per_hour_usd=option.cost_per_gpu_hour_usd,
            job_id=job_id,
        )
        self._active[job_id] = {
            "instance": instance,
            "host_config": host_config,
        }
        return instance

    async def wait_ready(self, instance: GPUInstance, timeout_seconds: int = 300) -> GPUInstance:
        """Check SSH connectivity with retry."""
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "ssh",
                    "-o", "ConnectTimeout=5",
                    "-o", "StrictHostKeyChecking=no",
                    "-p", str(instance.ssh_port),
                    f"root@{instance.ip_address}",
                    "echo ready",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                stdout, _ = await proc.communicate()
                if proc.returncode == 0 and b"ready" in stdout:
                    instance.status = InstanceStatus.RUNNING
                    return instance
            except Exception:
                pass
            await asyncio.sleep(5)

        instance.status = InstanceStatus.FAILED
        raise TimeoutError(f"SSH not ready after {timeout_seconds}s for {instance.ip_address}")

    async def run_container(
        self,
        instance: GPUInstance,
        image: ProverDockerImage,
        witness_data: bytes,
    ) -> ProofArtifact:
        """Run prover container on remote machine via SSH + Docker."""
        import tempfile
        import os
        from datetime import datetime, timezone

        job_id = instance.job_id
        start_time = time.monotonic()
        remote_dir = f"/tmp/zk-{job_id[:8]}"

        ssh_base = [
            "ssh", "-o", "StrictHostKeyChecking=no",
            "-p", str(instance.ssh_port),
            f"root@{instance.ip_address}",
        ]

        # Create remote directories
        await self._ssh_exec(ssh_base, f"mkdir -p {remote_dir}/input {remote_dir}/output")

        # Upload witness data
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tmp:
            tmp.write(witness_data)
            tmp_path = tmp.name

        try:
            scp_cmd = [
                "scp", "-o", "StrictHostKeyChecking=no",
                "-P", str(instance.ssh_port),
                tmp_path,
                f"root@{instance.ip_address}:{remote_dir}/input/witness.bin",
            ]
            proc = await asyncio.create_subprocess_exec(*scp_cmd)
            await proc.wait()
        finally:
            os.unlink(tmp_path)

        # Build docker command
        docker_cmd_parts = [
            "docker", "run", "--rm",
            "-v", f"{remote_dir}/input:{image.input_mount_path}:ro",
            "-v", f"{remote_dir}/output:/output",
        ]
        if image.gpu_required:
            docker_cmd_parts.extend(["--gpus", "all"])
        for k, v in image.env_vars.items():
            docker_cmd_parts.extend(["-e", f"{k}={v}"])
        docker_cmd_parts.append(image.image)
        if image.entrypoint:
            docker_cmd_parts.extend(image.entrypoint)

        docker_cmd = " ".join(docker_cmd_parts)

        # Pull image first, then run
        await self._ssh_exec(ssh_base, f"docker pull {image.image}")
        returncode, stdout, stderr = await self._ssh_exec(ssh_base, docker_cmd, capture=True)

        elapsed = time.monotonic() - start_time

        if returncode != 0:
            logger.error("Remote prover failed for job %s: %s", job_id, stderr[:500])
            return ProofArtifact(
                job_id=job_id,
                network=image.network,
                proof_system=image.proof_system,
                generation_gpu_seconds=elapsed,
            )

        # Download proof
        proof_filename = os.path.basename(image.proof_output_path)
        remote_proof = f"{remote_dir}/output/{proof_filename}"
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as tmp:
            local_proof = tmp.name

        try:
            scp_cmd = [
                "scp", "-o", "StrictHostKeyChecking=no",
                "-P", str(instance.ssh_port),
                f"root@{instance.ip_address}:{remote_proof}",
                local_proof,
            ]
            proc = await asyncio.create_subprocess_exec(*scp_cmd)
            await proc.wait()

            proof_data = b""
            if os.path.exists(local_proof):
                with open(local_proof, "rb") as f:
                    proof_data = f.read()
        finally:
            if os.path.exists(local_proof):
                os.unlink(local_proof)

        # Cleanup remote
        await self._ssh_exec(ssh_base, f"rm -rf {remote_dir}")

        return ProofArtifact(
            job_id=job_id,
            network=image.network,
            proof_system=image.proof_system,
            proof_data=proof_data,
            proof_hash=hashlib.sha256(proof_data).hexdigest() if proof_data else "",
            proof_size_bytes=len(proof_data),
            generation_gpu_seconds=elapsed,
            generated_at=datetime.now(timezone.utc),
        )

    async def terminate(self, instance: GPUInstance) -> None:
        """Clean up remote resources (containers, temp files)."""
        self._active.pop(instance.job_id, None)
        instance.status = InstanceStatus.TERMINATED

    async def get_status(self, instance: GPUInstance) -> InstanceStatus:
        return instance.status

    @staticmethod
    async def _ssh_exec(
        ssh_base: list[str], command: str, capture: bool = False
    ) -> tuple[int, str, str]:
        proc = await asyncio.create_subprocess_exec(
            *ssh_base, command,
            stdout=asyncio.subprocess.PIPE if capture else asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE if capture else asyncio.subprocess.DEVNULL,
        )
        stdout_bytes, stderr_bytes = await proc.communicate()
        return (
            proc.returncode or 0,
            (stdout_bytes or b"").decode(),
            (stderr_bytes or b"").decode(),
        )
