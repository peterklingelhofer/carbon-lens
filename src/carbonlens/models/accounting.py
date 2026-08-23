from datetime import datetime

from pydantic import BaseModel, Field


class EmissionsRecord(BaseModel):
    request_id: str
    timestamp: datetime
    chosen_provider: str
    chosen_region: str
    chosen_grid_zone: str
    chosen_carbon_intensity: float
    baseline_carbon_intensity: float = Field(
        description="Mean carbon intensity of the candidate regions considered -- the "
        "counterfactual of a carbon-blind pick among the same options."
    )
    intensity_reduction_gco2_kwh: float = Field(
        description="baseline_carbon_intensity - chosen_carbon_intensity (signed; negative "
        "means the chosen region was dirtier than the average candidate, e.g. cost-weighted)."
    )
    chosen_renewable_pct: float = 0.0


class ImpactIngest(BaseModel):
    """One carbon-aware run's impact, POSTed to the org ledger by a host."""

    region: str
    deferred_hours: int = 0
    reduction_gco2_kwh: float = 0.0
    energy_kwh: float | None = None
    basis: str = "forecast"


class CarbonSavingsReport(BaseModel):
    total_requests: int
    avg_intensity_reduction_gco2_kwh: float = Field(
        description="Average per-recommendation carbon-intensity reduction vs the baseline. A "
        "rate (gCO2/kWh), not a total: per-kWh intensities aren't additive across workloads, "
        "and real grams also depend on each job's energy use."
    )
    baseline: str = Field(description="The counterfactual the reduction is measured against.")
    avg_renewable_percentage: float
    records: list[EmissionsRecord]
