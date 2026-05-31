"""GPU compute provider abstraction — hyperscalers, green ASIC centers, alt-clouds.

Each provider exposes available GPUs with pricing, carbon data, and spin-up times.
The broker queries all providers and picks the greenest profitable option.
"""

from __future__ import annotations

import logging
from typing import Protocol, runtime_checkable

from carbon_mesh.carbon_sources.base import CarbonDataSource
from carbon_mesh.grid.mapper import GridMapper
from carbon_mesh.models.zk import (
    ComputeOption,
    ComputeProvider,
    GPUType,
)

logger = logging.getLogger(__name__)


@runtime_checkable
class GPUComputeAdapter(Protocol):
    """Protocol for GPU compute providers."""

    provider: ComputeProvider

    async def list_available(
        self,
        min_vram_gb: int = 0,
        gpu_type: GPUType | None = None,
    ) -> list[ComputeOption]: ...

    async def provision(
        self,
        option: ComputeOption,
        job_id: str,
    ) -> str:
        """Provision a GPU instance. Returns instance ID."""
        ...

    async def terminate(self, instance_id: str) -> None: ...


class MockGPUProvider:
    """Mock provider with realistic GPU options for development/demo.

    Simulates a mix of hyperscaler spot instances and green ASIC centers.
    """

    provider = ComputeProvider.AWS_SPOT  # overridden per-option

    async def list_available(
        self,
        min_vram_gb: int = 0,
        gpu_type: GPUType | None = None,
    ) -> list[ComputeOption]:
        options = [
            # --- Hyperscaler Spot (mixed grid) ---
            ComputeOption(
                provider=ComputeProvider.AWS_SPOT,
                region="us-east-1",
                gpu_type=GPUType.A100_40GB,
                gpu_count=1,
                vram_gb=40,
                cost_per_gpu_hour_usd=1.10,
                estimated_job_cost_usd=0.0,  # Filled by orchestrator
                grid_zone="US-MIDA-PJM",
                carbon_intensity_gco2_kwh=0.0,  # Filled by carbon lookup
                renewable_percentage=0.0,
                is_behind_the_meter=False,
                available=True,
                estimated_startup_seconds=90,
            ),
            ComputeOption(
                provider=ComputeProvider.AWS_SPOT,
                region="eu-west-1",
                gpu_type=GPUType.A100_40GB,
                gpu_count=1,
                vram_gb=40,
                cost_per_gpu_hour_usd=1.25,
                estimated_job_cost_usd=0.0,
                grid_zone="IE",
                carbon_intensity_gco2_kwh=0.0,
                renewable_percentage=0.0,
                is_behind_the_meter=False,
                available=True,
                estimated_startup_seconds=90,
            ),
            ComputeOption(
                provider=ComputeProvider.GCP_PREEMPTIBLE,
                region="us-central1",
                gpu_type=GPUType.T4,
                gpu_count=1,
                vram_gb=16,
                cost_per_gpu_hour_usd=0.35,
                estimated_job_cost_usd=0.0,
                grid_zone="US-MIDW-MISO",
                carbon_intensity_gco2_kwh=0.0,
                renewable_percentage=0.0,
                is_behind_the_meter=False,
                available=True,
                estimated_startup_seconds=60,
            ),
            ComputeOption(
                provider=ComputeProvider.GCP_PREEMPTIBLE,
                region="europe-west4",
                gpu_type=GPUType.A100_80GB,
                gpu_count=1,
                vram_gb=80,
                cost_per_gpu_hour_usd=1.85,
                estimated_job_cost_usd=0.0,
                grid_zone="NL",
                carbon_intensity_gco2_kwh=0.0,
                renewable_percentage=0.0,
                is_behind_the_meter=False,
                available=True,
                estimated_startup_seconds=120,
            ),
            # --- Green ASIC / Specialized Centers ---
            ComputeOption(
                provider=ComputeProvider.IREN,
                region="ca-bc-1",  # British Columbia, hydro
                gpu_type=GPUType.RTX_4090,
                gpu_count=1,
                vram_gb=24,
                cost_per_gpu_hour_usd=0.65,
                estimated_job_cost_usd=0.0,
                grid_zone="CA-BC",
                carbon_intensity_gco2_kwh=10.0,  # Near-zero (hydro)
                renewable_percentage=98.0,
                is_behind_the_meter=True,
                available=True,
                estimated_startup_seconds=30,
            ),
            ComputeOption(
                provider=ComputeProvider.TERAWULF,
                region="us-ny-lm",  # Lake Mariner, NY hydro
                gpu_type=GPUType.RTX_4090,
                gpu_count=1,
                vram_gb=24,
                cost_per_gpu_hour_usd=0.70,
                estimated_job_cost_usd=0.0,
                grid_zone="US-NY-NYIS",
                carbon_intensity_gco2_kwh=15.0,
                renewable_percentage=95.0,
                is_behind_the_meter=True,
                available=True,
                estimated_startup_seconds=20,
            ),
            ComputeOption(
                provider=ComputeProvider.HIVE_DIGITAL,
                region="is-reykjavik",  # Iceland, geothermal
                gpu_type=GPUType.A100_40GB,
                gpu_count=1,
                vram_gb=40,
                cost_per_gpu_hour_usd=0.90,
                estimated_job_cost_usd=0.0,
                grid_zone="IS",
                carbon_intensity_gco2_kwh=0.0,  # Zero carbon (geothermal)
                renewable_percentage=100.0,
                is_behind_the_meter=True,
                available=True,
                estimated_startup_seconds=15,
            ),
            ComputeOption(
                provider=ComputeProvider.HIVE_DIGITAL,
                region="se-stockholm",  # Sweden, hydro+wind
                gpu_type=GPUType.RTX_4090,
                gpu_count=1,
                vram_gb=24,
                cost_per_gpu_hour_usd=0.60,
                estimated_job_cost_usd=0.0,
                grid_zone="SE-SE3",
                carbon_intensity_gco2_kwh=8.0,
                renewable_percentage=99.0,
                is_behind_the_meter=True,
                available=True,
                estimated_startup_seconds=20,
            ),
            ComputeOption(
                provider=ComputeProvider.BITDEER,
                region="no-oslo",  # Norway, hydro
                gpu_type=GPUType.A100_80GB,
                gpu_count=1,
                vram_gb=80,
                cost_per_gpu_hour_usd=1.00,
                estimated_job_cost_usd=0.0,
                grid_zone="NO-NO1",
                carbon_intensity_gco2_kwh=5.0,
                renewable_percentage=99.0,
                is_behind_the_meter=True,
                available=True,
                estimated_startup_seconds=25,
            ),
            # --- Alt-Cloud GPU ---
            ComputeOption(
                provider=ComputeProvider.COREWEAVE,
                region="us-lga-1",  # New York
                gpu_type=GPUType.H100,
                gpu_count=1,
                vram_gb=80,
                cost_per_gpu_hour_usd=2.49,
                estimated_job_cost_usd=0.0,
                grid_zone="US-NY-NYIS",
                carbon_intensity_gco2_kwh=0.0,
                renewable_percentage=0.0,
                is_behind_the_meter=False,
                available=True,
                estimated_startup_seconds=45,
            ),
            ComputeOption(
                provider=ComputeProvider.LAMBDA_LABS,
                region="us-tx-1",  # Texas
                gpu_type=GPUType.A100_80GB,
                gpu_count=1,
                vram_gb=80,
                cost_per_gpu_hour_usd=1.29,
                estimated_job_cost_usd=0.0,
                grid_zone="US-TEX-ERCO",
                carbon_intensity_gco2_kwh=0.0,
                renewable_percentage=0.0,
                is_behind_the_meter=False,
                available=True,
                estimated_startup_seconds=60,
            ),
            ComputeOption(
                provider=ComputeProvider.VAST_AI,
                region="global",
                gpu_type=GPUType.RTX_4090,
                gpu_count=1,
                vram_gb=24,
                cost_per_gpu_hour_usd=0.40,
                estimated_job_cost_usd=0.0,
                grid_zone="US-MIDA-PJM",  # Varies — placeholder
                carbon_intensity_gco2_kwh=0.0,
                renewable_percentage=0.0,
                is_behind_the_meter=False,
                available=True,
                estimated_startup_seconds=120,
            ),
        ]

        # Filter by VRAM
        if min_vram_gb > 0:
            options = [o for o in options if o.vram_gb >= min_vram_gb]

        # Filter by GPU type
        if gpu_type:
            options = [o for o in options if o.gpu_type == gpu_type]

        return options

    async def provision(self, option: ComputeOption, job_id: str) -> str:
        """Mock provisioning — returns a fake instance ID."""
        return f"mock-{option.provider.value}-{job_id[:8]}"

    async def terminate(self, instance_id: str) -> None:
        logger.info("Mock terminate: %s", instance_id)


async def enrich_with_carbon(
    options: list[ComputeOption],
    carbon_source: CarbonDataSource,
    grid_mapper: GridMapper,
) -> list[ComputeOption]:
    """Enrich compute options with live carbon intensity data.

    Behind-the-meter facilities keep their pre-set values;
    grid-connected providers get live data from our 11 sources.
    """
    # Collect zones that need live data
    zones_to_fetch: list[str] = []
    for opt in options:
        if not opt.is_behind_the_meter and opt.grid_zone:
            zones_to_fetch.append(opt.grid_zone)

    if not zones_to_fetch:
        return options

    # Batch fetch
    unique_zones = list(set(zones_to_fetch))
    intensities = await carbon_source.get_carbon_intensity_batch(unique_zones)

    # Enrich
    enriched: list[ComputeOption] = []
    for opt in options:
        if not opt.is_behind_the_meter and opt.grid_zone in intensities:
            ci = intensities[opt.grid_zone]
            opt = opt.model_copy(
                update={
                    "carbon_intensity_gco2_kwh": ci.carbon_intensity_gco2_kwh,
                    "renewable_percentage": ci.renewable_percentage,
                }
            )
        enriched.append(opt)

    return enriched
