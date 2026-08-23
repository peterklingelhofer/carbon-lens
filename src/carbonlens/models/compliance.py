"""Domain models for GHG Protocol compliance reporting (Scope 2 & 3)."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class EmissionScope(str, Enum):
    """GHG Protocol emission scopes relevant to cloud infrastructure."""

    SCOPE_2 = "scope_2"  # Purchased electricity (location-based & market-based)
    SCOPE_3_CAT1 = "scope_3_cat1"  # Purchased goods/services (cloud compute)


class AccountingMethod(str, Enum):
    """GHG Protocol Scope 2 accounting methods."""

    LOCATION_BASED = "location_based"  # Grid-average emission factor
    MARKET_BASED = "market_based"  # Contractual (RECs, PPAs, residual mix)


class CloudUsageRecord(BaseModel):
    """A single cloud resource usage measurement for emissions calculation.

    Formula: emissions_kgco2e = energy_kwh * carbon_intensity_gco2_kwh / 1000
    Where:   energy_kwh = usage_quantity * energy_coefficient * pue
    """

    org_id: str
    provider: str  # aws, gcp, azure
    region: str
    service: str  # ec2, lambda, cloud-run, vm, s3, gcs, etc.
    resource_type: str  # e.g. "m5.xlarge", "Standard_D4s_v3"
    usage_quantity: float  # vCPU-hours, GB-hours, requests, etc.
    usage_unit: str  # "vcpu_hours", "gb_hours", "requests", "gb_transferred"
    energy_kwh: float = Field(ge=0, description="Estimated energy consumed in kWh")
    period_start: datetime
    period_end: datetime
    source: str = "manual"  # "aws_cur", "gcp_billing", "azure_cost", "manual"


class EmissionFactor(BaseModel):
    """Grid emission factor for a specific zone and time period."""

    grid_zone: str
    carbon_intensity_gco2_kwh: float = Field(ge=0)
    renewable_percentage: float = Field(ge=0, le=100)
    method: AccountingMethod
    timestamp: datetime
    source: str  # Which data provider supplied this
    data_quality: str = "measured"  # "measured", "modeled", "estimated", "default"


class EmissionsCalculation(BaseModel):
    """A single emissions calculation with full audit trail."""

    id: str
    org_id: str
    scope: EmissionScope
    method: AccountingMethod

    # What was measured
    provider: str
    region: str
    grid_zone: str
    service: str
    resource_type: str

    # Usage
    usage_quantity: float
    usage_unit: str
    energy_kwh: float

    # Emission factor applied
    emission_factor_gco2_kwh: float
    emission_factor_source: str
    emission_factor_quality: str

    # Result
    emissions_kgco2e: float = Field(ge=0, description="Total emissions in kg CO2 equivalent")
    renewable_percentage: float

    # PUE (Power Usage Effectiveness) — overhead for cooling, networking, etc.
    pue: float = Field(default=1.0, ge=1.0, description="Data center PUE applied")

    # Audit
    period_start: datetime
    period_end: datetime
    calculated_at: datetime
    methodology_version: str = "ghg_protocol_2024"


class ComplianceReport(BaseModel):
    """CSRD-aligned emissions report for a reporting period."""

    id: str
    org_id: str
    org_name: str
    report_name: str

    # Period
    period_start: datetime
    period_end: datetime
    generated_at: datetime

    # Scope 2 — location-based
    scope2_location_kgco2e: float
    scope2_location_by_provider: dict[str, float]  # {"aws": 123.4, "gcp": 56.7}
    scope2_location_by_region: dict[str, float]

    # Scope 2 — market-based
    scope2_market_kgco2e: float
    scope2_market_by_provider: dict[str, float]
    scope2_market_by_region: dict[str, float]

    # Scope 3 Category 1 (purchased cloud services)
    scope3_cat1_kgco2e: float
    scope3_cat1_by_provider: dict[str, float]
    scope3_cat1_by_service: dict[str, float]

    # Totals
    total_kgco2e: float
    total_energy_kwh: float
    avg_renewable_percentage: float
    total_cloud_regions_used: int
    total_providers_used: int

    # Optimization impact
    carbon_saved_kgco2e: float = Field(
        description="Estimated emissions avoided via carbon-aware routing"
    )
    carbon_saved_percentage: float

    # Methodology & audit
    methodology: str = "GHG Protocol Corporate Standard + Scope 2 Guidance (2015, updated 2023)"
    data_sources: list[str] = Field(
        default_factory=list,
        description="Carbon data sources used in this report",
    )
    data_quality_summary: dict[str, int] = Field(
        default_factory=dict,
        description="Count of calculations by data quality level",
    )
    reporting_standard: str = "CSRD / ESRS E1"
    calculation_count: int = 0

    # EU Taxonomy alignment
    eu_taxonomy_eligible: bool = True
    eu_taxonomy_aligned: bool = False  # Requires substantial contribution + DNSH
    taxonomy_notes: str = ""


class ComplianceReportSummary(BaseModel):
    """Lightweight report listing for API responses."""

    id: str
    report_name: str
    period_start: datetime
    period_end: datetime
    generated_at: datetime
    total_kgco2e: float
    total_energy_kwh: float
    carbon_saved_percentage: float


# --- Energy coefficients for cloud resource types ---
# These map usage units to kWh estimates.
# Sources: Etsy Cloud Jewels, CCF, Teads, AWS/GCP/Azure sustainability reports.

# vCPU-hour → kWh (varies by instance family, these are conservative averages)
VCPU_HOUR_KWH: dict[str, float] = {
    "default": 0.0035,  # ~3.5 Wh per vCPU-hour (CCF average)
    # AWS
    "m5": 0.0033,
    "m6i": 0.0028,
    "m6g": 0.0020,  # Graviton (ARM) — more efficient
    "c5": 0.0036,
    "c6i": 0.0030,
    "c6g": 0.0022,
    "r5": 0.0038,
    "r6i": 0.0032,
    "t3": 0.0025,
    # GCP
    "n2": 0.0032,
    "n2d": 0.0028,
    "e2": 0.0022,
    "c2": 0.0036,
    "t2a": 0.0020,  # Tau (ARM)
    # Azure
    "d_v5": 0.0030,
    "d_v4": 0.0033,
    "e_v5": 0.0032,
    "b_v2": 0.0025,
    "d_pv5": 0.0020,  # Cobalt (ARM)
}

# GB-hour storage → kWh
STORAGE_GB_HOUR_KWH: dict[str, float] = {
    "default": 0.000001,  # ~1 µWh per GB-hour (HDD)
    "ssd": 0.0000012,
    "hdd": 0.0000008,
    "s3": 0.0000006,
    "gcs": 0.0000006,
    "blob": 0.0000006,
}

# Networking: GB transferred → kWh
NETWORK_GB_KWH = 0.001  # ~1 Wh per GB (Coroama & Hilty estimates)

# Data center PUE by provider (public sustainability reports)
PROVIDER_PUE: dict[str, float] = {
    "aws": 1.135,  # AWS 2023 sustainability report
    "gcp": 1.10,  # Google 2023 (best-in-class)
    "azure": 1.18,  # Microsoft 2023 sustainability report
    "default": 1.20,
}
