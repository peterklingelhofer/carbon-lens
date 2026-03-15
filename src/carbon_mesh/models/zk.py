"""Domain models for the Green ZK Proof Broker.

Core flow:
1. Prover network posts a job (or we poll for available jobs)
2. Broker finds the cheapest, greenest GPU compute available
3. Only dispatches if carbon intensity <= max threshold
4. GPU spins up, generates proof, submits it
5. Broker collects bounty, takes margin, shuts down GPU
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


# --- Enums ---


class JobStatus(str, Enum):
    PENDING = "pending"  # Job received, awaiting dispatch
    ROUTING = "routing"  # Finding greenest compute
    DISPATCHED = "dispatched"  # Sent to GPU provider
    PROVING = "proving"  # GPU is generating the proof
    SUBMITTING = "submitting"  # Proof generated, submitting to network
    COMPLETED = "completed"  # Proof accepted, bounty earned
    FAILED = "failed"  # Proof generation or submission failed
    REJECTED = "rejected"  # No green compute available within threshold


class ProverNetwork(str, Enum):
    """Supported decentralized prover networks."""

    BOUNDLESS = "boundless"  # RISC Zero's prover marketplace
    SUCCINCT = "succinct"  # SP1 prover network
    GEVULOT = "gevulot"  # Decentralized proving layer
    ALEO = "aleo"  # Privacy-focused L1 with proving rewards
    SCROLL = "scroll"  # zkEVM rollup
    ZKSYNC = "zksync"  # zkSync Era prover
    STARKNET = "starknet"  # STARK-based rollup
    TAIKO = "taiko"  # Based contestable rollup


class ProofSystem(str, Enum):
    """ZK proof systems — determines GPU requirements."""

    GROTH16 = "groth16"  # Small proofs, trusted setup, GPU-friendly
    PLONK = "plonk"  # Universal setup, moderate GPU
    STARK = "stark"  # No trusted setup, CPU+GPU, large proofs
    HALO2 = "halo2"  # Recursive, no trusted setup (Scroll, zkSync)
    SP1 = "sp1"  # RISC-V zkVM (Succinct)
    RISC_ZERO = "risc_zero"  # RISC-V zkVM (RISC Zero / Boundless)
    NOVA = "nova"  # Folding scheme, incremental verification


class ComputeProvider(str, Enum):
    """GPU compute sources — from hyperscalers to green ASIC centers."""

    # Hyperscaler spot/preemptible
    AWS_SPOT = "aws_spot"
    GCP_PREEMPTIBLE = "gcp_preemptible"

    # Green specialized compute
    IREN = "iren"  # Iris Energy — 100% hydro (British Columbia)
    TERAWULF = "terawulf"  # Lake Mariner — 90%+ zero-carbon (NY hydro)
    HIVE_DIGITAL = "hive_digital"  # 100% green energy (Iceland, Sweden)
    BITDEER = "bitdeer"  # Hydro-powered facilities (Norway, Bhutan)

    # Alt-cloud GPU providers
    COREWEAVE = "coreweave"  # GPU-specialized cloud
    LAMBDA_LABS = "lambda_labs"  # GPU cloud for ML/crypto
    VAST_AI = "vast_ai"  # Decentralized GPU marketplace
    AKASH = "akash"  # Decentralized cloud (Cosmos)


class GPUType(str, Enum):
    """GPU models used for ZK proof generation."""

    RTX_4090 = "rtx_4090"  # Consumer top-end, great for ZK
    RTX_3080 = "rtx_3080"  # Solid mid-range prover
    A100_40GB = "a100_40gb"  # Data center standard
    A100_80GB = "a100_80gb"  # Large circuit proofs
    H100 = "h100"  # Fastest available
    L4 = "l4"  # Cost-effective inference/proving
    T4 = "t4"  # Budget option (AWS spot)


# --- Core models ---


class ProofJob(BaseModel):
    """A ZK proof generation job from a prover network."""

    id: str
    network: ProverNetwork
    proof_system: ProofSystem

    # Job details
    circuit_size: int = Field(description="Number of constraints (log2)")
    input_size_bytes: int = Field(description="Size of witness/input data")
    bounty_usd: float = Field(ge=0, description="Bounty in USD equivalent")
    bounty_token: str = Field(description="Token symbol (ETH, USDC, ALEO, etc.)")
    bounty_amount: float = Field(ge=0, description="Bounty in native token")
    deadline: datetime = Field(description="Proof must be submitted by this time")

    # Metadata
    posted_at: datetime
    requester: str = ""  # Wallet or contract address

    # Estimated requirements
    estimated_gpu_minutes: float = Field(ge=0, description="Estimated GPU time")
    min_vram_gb: int = Field(ge=0, description="Minimum VRAM required")


class ComputeOption(BaseModel):
    """An available GPU compute option with cost and carbon data."""

    provider: ComputeProvider
    region: str  # e.g. "us-east-1", "ca-bc-1", "is-reykjavik"
    gpu_type: GPUType
    gpu_count: int = 1
    vram_gb: int

    # Cost
    cost_per_gpu_hour_usd: float = Field(ge=0)
    estimated_job_cost_usd: float = Field(ge=0)

    # Carbon
    grid_zone: str
    carbon_intensity_gco2_kwh: float = Field(ge=0)
    renewable_percentage: float = Field(ge=0, le=100)
    is_behind_the_meter: bool = Field(
        default=False,
        description="True if facility draws directly from renewable source",
    )

    # Availability
    available: bool = True
    estimated_startup_seconds: int = 0  # Spot instance boot time


class DispatchDecision(BaseModel):
    """The broker's routing decision for a proof job."""

    job_id: str
    chosen_provider: ComputeOption
    rejected_options: list[ComputeOption] = []

    # Why this was chosen
    carbon_score: float = Field(description="0=zero carbon, 1=max carbon")
    cost_score: float = Field(description="0=cheapest, 1=most expensive")
    combined_score: float = Field(description="Weighted composite (lower=better)")

    # Economics
    estimated_profit_usd: float = Field(description="bounty - compute cost")
    profit_margin_pct: float = Field(description="Profit as % of bounty")

    # Carbon
    carbon_grams_co2: float = Field(description="Estimated emissions for this job")
    carbon_saved_vs_grid_avg_grams: float = Field(
        description="CO2 saved vs running on average grid"
    )

    dispatched_at: datetime


class JobResult(BaseModel):
    """Result of a completed (or failed) proof job."""

    job_id: str
    status: JobStatus

    # Proof
    proof_hash: str = ""  # Hash of the generated proof
    proof_size_bytes: int = 0
    verification_tx: str = ""  # On-chain verification transaction

    # Timing
    gpu_seconds: float = 0
    total_seconds: float = 0  # Including startup, submission
    started_at: datetime | None = None
    completed_at: datetime | None = None

    # Economics
    compute_cost_usd: float = 0
    bounty_earned_usd: float = 0
    profit_usd: float = 0

    # Carbon
    carbon_grams_co2: float = 0
    renewable_percentage: float = 0

    # Error
    error: str = ""


class BrokerStats(BaseModel):
    """Aggregate statistics for the broker dashboard."""

    # Jobs
    total_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    rejected_jobs: int = 0  # Rejected due to carbon threshold
    active_jobs: int = 0

    # Economics
    total_bounties_earned_usd: float = 0
    total_compute_cost_usd: float = 0
    total_profit_usd: float = 0
    avg_profit_margin_pct: float = 0

    # Carbon
    total_carbon_grams_co2: float = 0
    total_carbon_saved_grams: float = 0
    avg_renewable_percentage: float = 0
    zero_carbon_job_pct: float = 0  # % of jobs run on 100% renewable

    # Providers
    jobs_by_network: dict[str, int] = {}
    jobs_by_provider: dict[str, int] = {}
    earnings_by_network: dict[str, float] = {}


class CarbonPolicy(BaseModel):
    """Carbon policy configuration for the broker."""

    max_carbon_intensity_gco2_kwh: float = Field(
        default=50.0,
        ge=0,
        description="Maximum allowed carbon intensity. Set to 0 for zero-carbon only.",
    )
    prefer_behind_the_meter: bool = Field(
        default=True,
        description="Prefer facilities with direct renewable connections",
    )
    min_renewable_percentage: float = Field(
        default=80.0,
        ge=0,
        le=100,
        description="Minimum renewable energy percentage",
    )
    carbon_weight: float = Field(
        default=0.6,
        ge=0,
        le=1,
        description="Weight for carbon score in routing (vs cost)",
    )
    cost_weight: float = Field(
        default=0.4,
        ge=0,
        le=1,
        description="Weight for cost score in routing (vs carbon)",
    )
    min_profit_margin_pct: float = Field(
        default=10.0,
        description="Minimum profit margin to accept a job",
    )


# --- GPU power draw estimates (Watts TDP) ---

GPU_TDP_WATTS: dict[GPUType, int] = {
    GPUType.RTX_4090: 450,
    GPUType.RTX_3080: 320,
    GPUType.A100_40GB: 300,
    GPUType.A100_80GB: 300,
    GPUType.H100: 700,
    GPUType.L4: 72,
    GPUType.T4: 70,
}

# Proof system → typical GPU minutes per 2^20 constraints
PROOF_SYSTEM_GPU_MINUTES: dict[ProofSystem, float] = {
    ProofSystem.GROTH16: 2.0,
    ProofSystem.PLONK: 3.5,
    ProofSystem.STARK: 5.0,
    ProofSystem.HALO2: 4.0,
    ProofSystem.SP1: 3.0,
    ProofSystem.RISC_ZERO: 3.0,
    ProofSystem.NOVA: 2.5,
}
