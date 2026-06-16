"""Domain models for Green SLA monitoring and attestation."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SLAStatus(str, Enum):
    """Current compliance status of an SLA."""

    COMPLIANT = "compliant"
    WARNING = "warning"  # Close to threshold
    BREACHED = "breached"
    UNKNOWN = "unknown"  # Not enough data


class SLACheckFrequency(str, Enum):
    """How often to check SLA compliance."""

    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


class AlertChannel(str, Enum):
    """Where to send SLA breach alerts."""

    WEBHOOK = "webhook"
    # EMAIL and SLACK require account setup — add later
    # EMAIL = "email"
    # SLACK = "slack"


class GreenSLA(BaseModel):
    """A carbon SLA definition — the target a customer commits to."""

    id: str
    org_id: str
    name: str = Field(description="Human-readable SLA name")

    # Carbon targets
    max_carbon_intensity_gco2_kwh: float = Field(
        ge=0, description="Maximum allowed carbon intensity (gCO2/kWh)"
    )
    min_renewable_percentage: float = Field(
        ge=0, le=100, description="Minimum renewable energy percentage"
    )

    # Scope
    providers: list[str] = Field(
        default_factory=lambda: ["aws", "gcp", "azure"],
        description="Cloud providers covered by this SLA",
    )
    regions: list[str] = Field(
        default_factory=list,
        description="Specific regions to monitor (empty = all regions for the providers)",
    )

    # Monitoring
    check_frequency: SLACheckFrequency = SLACheckFrequency.HOURLY
    alert_channels: list[AlertChannel] = Field(default_factory=list)
    webhook_url: str = ""

    # Metadata
    created_at: datetime
    updated_at: datetime
    active: bool = True


class SLACheck(BaseModel):
    """A single SLA compliance check result."""

    id: str
    sla_id: str
    checked_at: datetime

    # Results
    status: SLAStatus
    avg_carbon_intensity_gco2_kwh: float
    max_carbon_intensity_gco2_kwh: float
    min_carbon_intensity_gco2_kwh: float
    avg_renewable_percentage: float

    # Details
    regions_checked: int
    regions_compliant: int
    regions_breached: int
    breached_regions: list[dict] = Field(
        default_factory=list,
        description="List of regions that breached the SLA with details",
    )

    # Thresholds at time of check
    target_max_carbon: float
    target_min_renewable: float


class SLAReport(BaseModel):
    """Attestation report for a Green SLA over a period."""

    id: str
    sla_id: str
    org_id: str
    org_name: str
    sla_name: str

    # Period
    period_start: datetime
    period_end: datetime
    generated_at: datetime

    # Summary
    total_checks: int
    compliant_checks: int
    warning_checks: int
    breached_checks: int
    compliance_percentage: float = Field(
        ge=0, le=100, description="Percentage of checks that were compliant"
    )

    # Aggregated metrics
    avg_carbon_intensity_gco2_kwh: float
    max_carbon_intensity_gco2_kwh: float
    avg_renewable_percentage: float
    min_renewable_percentage: float

    # SLA targets
    target_max_carbon: float
    target_min_renewable: float

    # Breakdown
    checks_by_day: dict[str, dict] = Field(
        default_factory=dict,
        description="Daily compliance summary: date -> {status, avg_carbon, avg_renewable}",
    )
    worst_regions: list[dict] = Field(
        default_factory=list,
        description="Top regions with highest carbon intensity during period",
    )
    best_regions: list[dict] = Field(
        default_factory=list,
        description="Top regions with lowest carbon intensity during period",
    )

    # Attestation
    methodology: str = "Real-time grid carbon intensity from government-verified sources"
    data_sources: list[str] = Field(default_factory=list)
    reporting_standard: str = "Carbon Lens Green SLA Attestation v1"


class SLASummary(BaseModel):
    """Lightweight SLA listing for API responses."""

    id: str
    name: str
    org_id: str
    status: SLAStatus
    max_carbon_intensity_gco2_kwh: float
    min_renewable_percentage: float
    check_frequency: SLACheckFrequency
    last_checked: datetime | None = None
    active: bool


class AlertEvent(BaseModel):
    """A record of an SLA breach alert that was sent."""

    id: str
    sla_id: str
    sla_name: str
    channel: AlertChannel
    sent_at: datetime
    status: SLAStatus
    details: dict = Field(default_factory=dict)
    delivery_status: str = "sent"  # "sent", "failed", "pending"
