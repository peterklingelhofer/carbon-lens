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
    clean_surplus_hours: list[int] = Field(
        default_factory=list,
        description="Hour offsets (0 = now) projected to be clean surplus -- renewables "
        "dominant and very low carbon, so extra load likely soaks up power that would "
        "otherwise be curtailed. The highest-value windows to shift flexible load into. "
        "A heuristic from the projected mix, not measured curtailment.",
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
    marginal_intensity_gco2_kwh: float | None = Field(
        default=None,
        description="Estimated emissions of an extra kWh of demand now -- the number that "
        "actually responds to shifting load. Heuristic from the fuel mix; null when no live "
        "fuel mix is available.",
    )
    marginal_note: str | None = Field(
        default=None,
        description="Plain-English caveat when the marginal picture changes the decision "
        "(e.g. clean on average but fossil on the margin), or null when nothing notable.",
    )
    clean_surplus: bool = Field(
        default=False,
        description="True when the grid looks like clean oversupply now -- renewables "
        "dominant, very low carbon, clean margin -- so extra load likely soaks up power "
        "that would otherwise be curtailed. The highest-value moment to run flexible jobs. "
        "A heuristic, not measured curtailment.",
    )
    surplus_window_in_hours: int | None = Field(
        default=None,
        description="Hours until the soonest upcoming clean-surplus window in the forecast "
        "(null if none ahead, or if now is already surplus). The best time to shift a "
        "flexible job to, even when now is merely 'cleaner'.",
    )


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


class HourRank(BaseModel):
    hour_utc: int = Field(ge=0, le=23)
    mean_gco2_kwh: float
    samples: int


class BestTime(BaseModel):
    """The greenest hour-of-day to run a recurring job, for picking a cron schedule."""

    provider: str
    region: str
    grid_zone: str
    basis: str = Field(
        description="history (observed hour-of-day means), forecast (next-48h curve as a "
        "proxy), or insufficient (no data yet)"
    )
    days_analyzed: int
    cleanest_hour_utc: int | None = Field(
        default=None, description="The lowest-mean-intensity UTC hour, or null if no data"
    )
    dirtiest_hour_utc: int | None = Field(
        default=None, description="The highest-mean-intensity UTC hour, for contrast"
    )
    shift_savings_pct: float | None = Field(
        default=None,
        description="How much cleaner the best hour is than the worst observed hour (%). The "
        "value of scheduling well vs scheduling badly.",
    )
    annual_kg_saved: float | None = Field(
        default=None,
        description="If a daily job of the given --energy-kwh moved from the worst to the best "
        "hour: estimated kg CO2 avoided per year (assumes the pattern holds). Null without energy.",
    )
    suggested_cron: str | None = Field(
        default=None, description="A daily crontab line for the cleanest hour (UTC), or null"
    )
    ranked_hours: list[HourRank] = Field(
        default_factory=list, description="Cleanest hours first (top few)"
    )


class WeatherConditions(BaseModel):
    """Current weather at a region's coordinates -- the physical drivers behind its
    renewable output. Wind turns turbines; sunlight drives solar. A single-point
    proxy for a whole grid zone, from Open-Meteo (free, no key)."""

    grid_zone: str
    provider: str
    region: str
    wind_speed_kmh: float = Field(
        ge=0, description="Surface wind speed at 10 m, in km/h (drives wind generation)"
    )
    solar_irradiance_w_m2: float = Field(
        ge=0,
        description="Shortwave solar irradiance at the surface, in W/m2 (drives solar generation)",
    )
    observed_at: datetime
    source: str = "open_meteo"
