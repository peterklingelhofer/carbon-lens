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


class CarbonForecast(BaseModel):
    grid_zone: str
    provider: str
    region: str
    generated_at: datetime
    method: str = Field(
        description="How the curve was produced: 'entsoe_day_ahead' (real EU "
        "day-ahead wind/solar/load forecast) or 'time_of_day_model' (a local "
        "time-of-day heuristic, not a measured forecast).",
    )
    points: list[CarbonIntensity] = Field(
        description="Hour-by-hour projection over the horizon; the first point is "
        "the current reading.",
    )


class CarbonSignal(BaseModel):
    """A one-call decision primitive: should a flexible job run here now, or wait?

    Designed for the carbon-aware-dispatcher and any script/status page that just
    wants a traffic-light answer plus the next cleaner window.
    """

    provider: str
    region: str
    grid_zone: str
    intensity_gco2_kwh: float
    state: str = Field(description="green | yellow | red, by absolute intensity thresholds")
    advice: str = Field(description="run_now | wait_for_cleaner")
    cleaner_window_in_hours: int | None = Field(
        default=None,
        description="Hours until a notably cleaner upcoming window, or null if now is fine",
    )
    cleaner_window_intensity_gco2_kwh: float | None = None


class CarbonAnomaly(BaseModel):
    """Whether a zone is cleaner or dirtier than its own historical baseline now."""

    provider: str
    region: str
    grid_zone: str
    current_gco2_kwh: float
    baseline_gco2_kwh: float | None = None
    delta_pct: float | None = Field(
        default=None, description="Signed; negative = cleaner than usual"
    )
    status: str = Field(
        description="cleaner_than_usual | typical | dirtier_than_usual | insufficient_history"
    )
    basis: str = Field(description="hour_of_day | recent | insufficient")
    sample_size: int


class CarbonHistoryPoint(BaseModel):
    timestamp: datetime
    carbon_intensity_gco2_kwh: float = Field(ge=0)
    renewable_percentage: float = Field(ge=0, le=100)


class CarbonHistory(BaseModel):
    grid_zone: str
    provider: str
    region: str
    points: list[CarbonHistoryPoint] = Field(
        description="Past readings for this region, oldest first, from the "
        "published rolling history archive. Empty until the archive accumulates.",
    )
