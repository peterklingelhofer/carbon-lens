from datetime import datetime

from pydantic import BaseModel, Field, model_validator

VALID_PROVIDERS = {"aws", "gcp", "azure"}


class JobConstraints(BaseModel):
    providers: list[str] = Field(
        description="Cloud providers to consider, e.g. ['aws', 'gcp', 'azure']",
        min_length=1,
    )
    candidate_regions: list[str] | None = Field(
        default=None,
        description="Specific regions to consider. None = all regions for selected providers.",
    )
    data_residency: list[str] | None = Field(
        default=None,
        description="Restrict to regions in these countries/continents, e.g. ['EU', 'US']",
    )
    carbon_weight: float = Field(default=0.7, ge=0, le=1, description="Weight for carbon score")
    cost_weight: float = Field(default=0.3, ge=0, le=1, description="Weight for cost score")

    @model_validator(mode="after")
    def validate_constraints(self) -> "JobConstraints":
        unknown = set(self.providers) - VALID_PROVIDERS
        if unknown:
            raise ValueError(f"Unknown providers: {unknown}. Valid: {sorted(VALID_PROVIDERS)}")
        if self.carbon_weight + self.cost_weight == 0:
            raise ValueError("carbon_weight + cost_weight must be > 0")
        return self


class RouteRequest(BaseModel):
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "constraints": {
                        "providers": ["aws", "gcp"],
                        "carbon_weight": 1.0,
                        "cost_weight": 0.0,
                    }
                },
                {
                    "constraints": {
                        "providers": ["aws", "gcp", "azure"],
                        "data_residency": ["EU"],
                        "carbon_weight": 0.7,
                        "cost_weight": 0.3,
                    }
                },
            ]
        }
    }

    constraints: JobConstraints


class RegionRecommendation(BaseModel):
    provider: str
    region: str
    grid_zone: str
    carbon_intensity_gco2_kwh: float
    renewable_percentage: float
    score: float = Field(description="Composite score (lower is better)")
    carbon_savings_vs_worst_pct: float = Field(
        description="Percentage greener than worst candidate"
    )


class RouteResponse(BaseModel):
    recommended: RegionRecommendation
    alternatives: list[RegionRecommendation]
    request_id: str
    timestamp: datetime
