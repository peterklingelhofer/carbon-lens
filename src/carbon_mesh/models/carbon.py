from datetime import datetime

from pydantic import BaseModel, Field


class CarbonIntensity(BaseModel):
    grid_zone: str
    carbon_intensity_gco2_kwh: float = Field(ge=0, description="Grams CO2 per kWh")
    renewable_percentage: float = Field(ge=0, le=100)
    timestamp: datetime
    source: str
    grid_load_mw: float | None = Field(
        default=None,
        ge=0,
        description="Total grid generation/load for the balancing authority in MW "
        "(whole grid, all consumers — not datacenter-specific). None when the "
        "source does not report it.",
    )
    marginal_intensity_gco2_kwh: float | None = Field(
        default=None,
        ge=0,
        description="Estimated marginal emission factor (what an extra kWh of demand "
        "would emit). A heuristic from the fuel mix, not measured marginal data. "
        "None for sources without a real fuel mix.",
    )
    power_breakdown_mw: dict[str, float] | None = Field(
        default=None,
        description="Live generation breakdown by fuel type in MW (e.g. "
        '{"wind": 4200, "natural_gas": 1800, "nuclear": 9500}). Only the fuels '
        "actually generating are listed. None for sources without a real fuel mix "
        "(heuristic and weather-based estimates).",
    )
