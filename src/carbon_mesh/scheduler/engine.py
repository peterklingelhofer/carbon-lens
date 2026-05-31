"""Carbon-aware scheduling engine — find optimal low-carbon time windows.

Given a job duration and a scheduling window, this engine evaluates carbon
intensity across time slots and regions to find the greenest execution window.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from enum import Enum

from pydantic import BaseModel, Field

from carbon_mesh.carbon_sources.base import CarbonDataSource
from carbon_mesh.grid.mapper import GridMapper
from carbon_mesh.models.carbon import CarbonIntensity


class ScheduleStrategy(str, Enum):
    """How to optimize the schedule."""

    LOWEST_CARBON = "lowest_carbon"  # Pick time with lowest gCO2/kWh
    HIGHEST_RENEWABLE = "highest_renewable"  # Pick time with highest renewable %
    BALANCED = "balanced"  # Weighted combination


class TimeSlot(BaseModel):
    """A candidate time window for scheduling."""

    start: datetime
    end: datetime
    provider: str
    region: str
    grid_zone: str
    carbon_intensity_gco2_kwh: float
    renewable_percentage: float
    score: float = Field(description="Lower is better for carbon, higher for renewable")


class ScheduleRecommendation(BaseModel):
    """Recommendation for when and where to run a job."""

    id: str
    recommended: TimeSlot
    alternatives: list[TimeSlot]
    job_duration_minutes: int
    window_start: datetime
    window_end: datetime
    strategy: ScheduleStrategy
    carbon_saved_vs_now_pct: float = Field(
        description="Percentage of carbon saved vs running immediately"
    )
    evaluated_slots: int


class CronSchedule(BaseModel):
    """A recurring job with carbon-aware scheduling."""

    id: str
    name: str
    org_id: str
    job_duration_minutes: int = Field(ge=1, le=1440)
    providers: list[str] = Field(default_factory=lambda: ["aws", "gcp", "azure"])
    preferred_regions: list[str] = Field(default_factory=list)
    strategy: ScheduleStrategy = ScheduleStrategy.LOWEST_CARBON
    max_delay_hours: int = Field(
        ge=1, le=168, default=24, description="Max hours to delay for green window"
    )
    created_at: datetime
    active: bool = True


class SchedulingEngine:
    """Finds optimal low-carbon time windows for batch jobs.

    Evaluates carbon intensity across a time window by sampling at intervals
    and scoring each slot. For real-time data, the "forecast" is based on
    current conditions + time-of-day heuristics (solar peaks midday,
    wind varies, hydro is steady).
    """

    def __init__(
        self,
        carbon_source: CarbonDataSource,
        grid_mapper: GridMapper,
    ) -> None:
        self._carbon_source = carbon_source
        self._grid_mapper = grid_mapper

    async def find_optimal_window(
        self,
        job_duration_minutes: int,
        providers: list[str],
        preferred_regions: list[str] | None = None,
        strategy: ScheduleStrategy = ScheduleStrategy.LOWEST_CARBON,
        max_delay_hours: int = 24,
    ) -> ScheduleRecommendation:
        """Find the best time and region to run a job.

        Evaluates carbon intensity across regions right now and estimates
        future windows using time-of-day heuristics.
        """
        now = datetime.now(timezone.utc)
        window_end = now + timedelta(hours=max_delay_hours)

        # Get all regions for the specified providers
        regions = self._resolve_regions(providers, preferred_regions)

        # Fetch current carbon intensity for all regions
        zone_map: dict[str, tuple[str, str]] = {}
        zones: list[str] = []
        for provider, region in regions:
            zone = self._grid_mapper.get_grid_zone(provider, region)
            if zone and zone not in zones:
                zone_map[zone] = (provider, region)
                zones.append(zone)

        current_intensities = await self._carbon_source.get_carbon_intensity_batch(zones)

        # Build time slots: current + projected slots at intervals
        slots: list[TimeSlot] = []
        slot_interval_hours = max(
            1, max_delay_hours // 24
        )  # 1-hour slots for 24h, larger for longer windows

        for hour_offset in range(0, max_delay_hours, slot_interval_hours):
            slot_start = now + timedelta(hours=hour_offset)
            slot_end = slot_start + timedelta(minutes=job_duration_minutes)

            if slot_end > window_end + timedelta(minutes=job_duration_minutes):
                break

            for zone, (provider, region) in zone_map.items():
                current = current_intensities.get(zone)
                if not current:
                    continue

                # Apply time-of-day heuristic to project future carbon intensity
                projected = self._project_intensity(current, hour_offset)

                score = self._score_slot(projected, strategy)

                slots.append(
                    TimeSlot(
                        start=slot_start,
                        end=slot_end,
                        provider=provider,
                        region=region,
                        grid_zone=zone,
                        carbon_intensity_gco2_kwh=projected.carbon_intensity_gco2_kwh,
                        renewable_percentage=projected.renewable_percentage,
                        score=score,
                    )
                )

        if not slots:
            # Fallback: return "now" with first available region
            first_zone = zones[0] if zones else "unknown"
            first_prov, first_reg = zone_map.get(first_zone, ("unknown", "unknown"))
            first_intensity = current_intensities.get(first_zone)
            fallback = TimeSlot(
                start=now,
                end=now + timedelta(minutes=job_duration_minutes),
                provider=first_prov,
                region=first_reg,
                grid_zone=first_zone,
                carbon_intensity_gco2_kwh=first_intensity.carbon_intensity_gco2_kwh
                if first_intensity
                else 0,
                renewable_percentage=first_intensity.renewable_percentage if first_intensity else 0,
                score=0,
            )
            return ScheduleRecommendation(
                id=str(uuid.uuid4()),
                recommended=fallback,
                alternatives=[],
                job_duration_minutes=job_duration_minutes,
                window_start=now,
                window_end=window_end,
                strategy=strategy,
                carbon_saved_vs_now_pct=0,
                evaluated_slots=0,
            )

        # Sort by score (lower is better for carbon, we want lowest carbon)
        if strategy == ScheduleStrategy.HIGHEST_RENEWABLE:
            slots.sort(key=lambda s: -s.score)  # Higher renewable = better
        else:
            slots.sort(key=lambda s: s.score)  # Lower carbon = better

        recommended = slots[0]
        alternatives = slots[1:10]  # Top 10 alternatives

        # Calculate savings vs running right now at worst region
        now_slots = [s for s in slots if s.start == now]
        if now_slots:
            now_worst = max(s.carbon_intensity_gco2_kwh for s in now_slots)
            if now_worst > 0:
                saved_pct = round((1 - recommended.carbon_intensity_gco2_kwh / now_worst) * 100, 1)
            else:
                saved_pct = 0.0
        else:
            saved_pct = 0.0

        return ScheduleRecommendation(
            id=str(uuid.uuid4()),
            recommended=recommended,
            alternatives=alternatives,
            job_duration_minutes=job_duration_minutes,
            window_start=now,
            window_end=window_end,
            strategy=strategy,
            carbon_saved_vs_now_pct=max(saved_pct, 0),
            evaluated_slots=len(slots),
        )

    def _project_intensity(self, current: CarbonIntensity, hours_ahead: int) -> CarbonIntensity:
        """Project carbon intensity forward using time-of-day heuristics.

        This is a simplified model. Real forecasting would use weather data,
        grid operator forecasts, and ML models. For now we apply basic
        solar/demand cycle adjustments.
        """
        if hours_ahead == 0:
            return current

        now = datetime.now(timezone.utc)
        future_hour = (now.hour + hours_ahead) % 24

        # Solar generation peaks 10am-3pm local (rough UTC approximation)
        # Demand peaks 6pm-9pm, lowest 2am-5am
        solar_factor = self._solar_factor(future_hour)
        demand_factor = self._demand_factor(future_hour)

        # Project: lower demand + higher solar = lower carbon
        adjustment = 1.0 + (demand_factor - solar_factor) * 0.15

        projected_carbon = max(0, current.carbon_intensity_gco2_kwh * adjustment)
        projected_renewable = min(
            100, max(0, current.renewable_percentage * (1 + solar_factor * 0.1))
        )

        return CarbonIntensity(
            grid_zone=current.grid_zone,
            carbon_intensity_gco2_kwh=round(projected_carbon, 2),
            renewable_percentage=round(projected_renewable, 1),
            timestamp=now + timedelta(hours=hours_ahead),
            source=f"{current.source} (projected +{hours_ahead}h)",
        )

    @staticmethod
    def _solar_factor(hour_utc: int) -> float:
        """Solar generation factor (0-1) by UTC hour. Peaks midday."""
        # Bell curve centered around noon UTC (rough global average)
        if 6 <= hour_utc <= 18:
            # Parabolic approximation peaking at noon
            return max(0, 1 - ((hour_utc - 12) / 6) ** 2)
        return 0.0

    @staticmethod
    def _demand_factor(hour_utc: int) -> float:
        """Electricity demand factor (0-1) by UTC hour. Peaks evening."""
        # Higher demand 7am-10pm, peak at 6pm
        if 7 <= hour_utc <= 22:
            if 17 <= hour_utc <= 20:
                return 1.0  # Peak
            elif 7 <= hour_utc <= 9:
                return 0.7  # Morning ramp
            else:
                return 0.5  # Daytime baseline
        return 0.2  # Overnight low

    @staticmethod
    def _score_slot(intensity: CarbonIntensity, strategy: ScheduleStrategy) -> float:
        """Score a time slot. Lower = better for carbon strategies."""
        if strategy == ScheduleStrategy.LOWEST_CARBON:
            return intensity.carbon_intensity_gco2_kwh
        elif strategy == ScheduleStrategy.HIGHEST_RENEWABLE:
            return intensity.renewable_percentage  # Higher = better, sorted descending
        else:
            # Balanced: weighted combination
            carbon_score = intensity.carbon_intensity_gco2_kwh / 500  # Normalize to 0-1
            renewable_score = 1 - (intensity.renewable_percentage / 100)  # Lower = more renewable
            return carbon_score * 0.6 + renewable_score * 0.4

    def _resolve_regions(
        self,
        providers: list[str],
        preferred_regions: list[str] | None,
    ) -> list[tuple[str, str]]:
        """Resolve to a list of (provider, region) tuples."""
        if preferred_regions:
            result: list[tuple[str, str]] = []
            for provider in providers:
                for region in preferred_regions:
                    if self._grid_mapper.get_grid_zone(provider, region):
                        result.append((provider, region))
            return result

        all_regions = self._grid_mapper.list_regions()
        return [(r.provider, r.region) for r in all_regions if r.provider in providers]
