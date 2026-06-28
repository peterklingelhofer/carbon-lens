"""Carbon-aware scheduling engine — find optimal low-carbon time windows.

Given a job duration and a scheduling window, this engine evaluates carbon
intensity across time slots and regions to find the greenest execution window.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from enum import Enum

from pydantic import BaseModel, Field

from carbon_mesh.carbon_sources.base import CarbonDataSource
from carbon_mesh.carbon_sources.entsoe_forecast import ENTSOEForecastSource
from carbon_mesh.carbon_sources.open_meteo import OpenMeteoForecastSource
from carbon_mesh.engine.surplus import is_clean_surplus
from carbon_mesh.grid.mapper import GridMapper
from carbon_mesh.models.carbon import CarbonIntensity

# Fetch real day-ahead forecasts only for the cleanest-right-now EU zones (the
# recommendation almost always comes from these). Bounds the per-request API
# fan-out; other zones use the local-time heuristic.
_FORECAST_TOP_K = 4

# A clean-surplus slot ranks as if it were this much cleaner: extra load then has
# near-zero marginal emissions (it soaks up would-be-curtailed renewables), which
# is the right thing to optimise for. Bounded so a substantially cleaner non-surplus
# slot still wins -- the edge breaks ties and close calls, it doesn't override big gaps.
_SURPLUS_DISCOUNT = 0.4


class ScheduleStrategy(str, Enum):
    """How to optimize the schedule."""

    LOWEST_CARBON = "lowest_carbon"
    HIGHEST_RENEWABLE = "highest_renewable"
    BALANCED = "balanced"  # weighted carbon + renewable combination


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
    clean_surplus: bool = Field(
        default=False,
        description="True when this slot looks like clean oversupply -- renewables dominant, "
        "very low carbon -- so it's the highest-value time to run (near-zero marginal). "
        "Given a bounded ranking edge. A heuristic, not measured curtailment.",
    )


class ScheduleRecommendation(BaseModel):
    """Recommendation for when and where to run a job."""

    id: str
    recommended: TimeSlot
    alternatives: list[TimeSlot]
    forecast: list[TimeSlot] = Field(
        default_factory=list,
        description="The recommended region's hourly intensity curve across the window",
    )
    job_duration_minutes: int
    window_start: datetime
    window_end: datetime
    strategy: ScheduleStrategy
    carbon_saved_vs_now_pct: float = Field(
        description="Percentage of carbon saved vs running immediately"
    )
    evaluated_slots: int
    marginal_basis: str = Field(
        default="heuristic",
        description="Whether the recommended region's marginal signal is 'measured' (from a "
        "configured marginal source) or 'heuristic' (a merit-order estimate)",
    )


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
        forecast_source: ENTSOEForecastSource | None = None,
        weather_forecast_source: OpenMeteoForecastSource | None = None,
        marginal_source=None,
    ) -> None:
        self._carbon_source = carbon_source
        self._grid_mapper = grid_mapper
        self._forecast_source = forecast_source
        self._weather_forecast_source = weather_forecast_source
        # Optional measured-marginal source (WattTime). When present, forecast points
        # carry MEASURED marginal so surplus/decisions are marginal-correct, not heuristic.
        self._marginal_source = marginal_source

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
        now = datetime.now(UTC)
        window_end = now + timedelta(hours=max_delay_hours)

        # Get all regions for the specified providers
        regions = self._resolve_regions(providers, preferred_regions)

        # Fetch current carbon intensity for all regions
        zone_map: dict[str, tuple[str, str]] = {}
        zone_lng: dict[str, float] = {}
        zones: list[str] = []
        for provider, region in regions:
            zone = self._grid_mapper.get_grid_zone(provider, region)
            if zone and zone not in zones:
                zone_map[zone] = (provider, region)
                info = self._grid_mapper.get_region(provider, region)
                zone_lng[zone] = info.longitude if info else 0.0
                zones.append(zone)

        current_intensities = await self._carbon_source.get_carbon_intensity_batch(zones)

        # Real day-ahead forecast curves for any ENTSO-E (EU) zones, fetched once
        # per zone. Maps zone -> {hour_offset: forecasted VRE share of load}.
        zone_curve: dict[str, dict[int, float]] = {}
        if self._forecast_source:
            eu_zones = [
                z
                for z in zones
                if z in current_intensities and self._forecast_source.can_forecast(z)
            ]
            # Cleanest-now first; only the top few get a real forecast fetch.
            eu_zones.sort(key=lambda z: current_intensities[z].carbon_intensity_gco2_kwh)
            fc_zones = eu_zones[:_FORECAST_TOP_K]
            settled = await asyncio.gather(
                *(self._forecast_source.vre_fraction_curve(z, max_delay_hours) for z in fc_zones),
                return_exceptions=True,
            )
            for z, curve in zip(fc_zones, settled):
                if isinstance(curve, dict) and curve:
                    zone_curve[z] = curve

        # Build time slots: current + projected slots at intervals
        slots: list[TimeSlot] = []
        # 1-hour slots for a 24h window, coarser for longer windows
        slot_interval_hours = max(1, max_delay_hours // 24)

        # A job runs ACROSS hours, so score each candidate by the AVERAGE projected
        # intensity over its whole run window, not just the start hour -- a long job
        # that starts clean but runs into a dirty morning ramp should rank by what it
        # actually emits. (A sub-hour job -> a single hour, so behaviour is unchanged.)
        duration_hours = max(1, (job_duration_minutes + 59) // 60)

        for hour_offset in range(0, max_delay_hours, slot_interval_hours):
            slot_start = now + timedelta(hours=hour_offset)
            slot_end = slot_start + timedelta(minutes=job_duration_minutes)

            for zone, (provider, region) in zone_map.items():
                current = current_intensities.get(zone)
                if not current:
                    continue

                curve = zone_curve.get(zone)
                window = [
                    self._project_at(current, curve, hour_offset + d, zone_lng.get(zone, 0.0))
                    for d in range(duration_hours)
                ]
                avg_carbon = round(
                    sum(p.carbon_intensity_gco2_kwh for p in window) / len(window), 2
                )
                avg_renewable = round(sum(p.renewable_percentage for p in window) / len(window), 1)

                # Representative intensity over the run window (projection -> no marginal).
                averaged = CarbonIntensity(
                    grid_zone=zone,
                    carbon_intensity_gco2_kwh=avg_carbon,
                    renewable_percentage=avg_renewable,
                    timestamp=slot_start,
                    source=window[0].source,
                )
                surplus = is_clean_surplus(avg_renewable, avg_carbon, None)
                score = self._score_slot(averaged, strategy, surplus)

                slots.append(
                    TimeSlot(
                        start=slot_start,
                        end=slot_end,
                        provider=provider,
                        region=region,
                        grid_zone=zone,
                        carbon_intensity_gco2_kwh=avg_carbon,
                        renewable_percentage=avg_renewable,
                        score=score,
                        clean_surplus=surplus,
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
                marginal_basis=self._marginal_basis_for(first_zone),
            )

        # Sort by score
        if strategy == ScheduleStrategy.HIGHEST_RENEWABLE:
            slots.sort(key=lambda s: -s.score)  # Higher renewable = better
        else:
            slots.sort(key=lambda s: s.score)  # Lower carbon = better

        recommended = slots[0]
        alternatives = slots[1:10]  # up to 9 runners-up (recommended + these = top 10)

        # The recommended region's full hourly curve over the window, so the UI
        # can plot how its intensity evolves and where the chosen slot sits.
        forecast = sorted(
            (
                s
                for s in slots
                if s.provider == recommended.provider and s.region == recommended.region
            ),
            key=lambda s: s.start,
        )

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
            forecast=forecast,
            job_duration_minutes=job_duration_minutes,
            window_start=now,
            window_end=window_end,
            strategy=strategy,
            carbon_saved_vs_now_pct=max(saved_pct, 0),
            evaluated_slots=len(slots),
            marginal_basis=self._marginal_basis_for(recommended.grid_zone),
        )

    def _marginal_basis_for(self, grid_zone: str) -> str:
        """'measured' when a configured marginal source covers this zone, else 'heuristic'."""
        if self._marginal_source is not None and self._marginal_source.can_handle(grid_zone):
            return "measured"
        return "heuristic"

    async def forecast_zone(
        self,
        grid_zone: str,
        longitude: float = 0.0,
        hours: int = 24,
    ) -> tuple[str, list[CarbonIntensity]]:
        """Project one zone's carbon intensity hour-by-hour over the horizon.

        Point 0 is the current reading. EU zones with an ENTSO-E day-ahead forecast
        are scaled by the forecast VRE share; elsewhere the local time-of-day model
        is used. Returns ``(method, points)`` so callers can label provenance.
        """
        current = await self._carbon_source.get_carbon_intensity(grid_zone)

        # Prefer ENTSO-E's real day-ahead forecast (EU); fall back to Open-Meteo's
        # weather forecast for the weather-estimated zones; else a time-of-day model.
        curve: dict[int, float] = {}
        method = "time_of_day_model"
        for source, label in (
            (self._forecast_source, "entsoe_day_ahead"),
            (self._weather_forecast_source, "open_meteo_forecast"),
        ):
            if source and source.can_forecast(grid_zone):
                try:
                    fetched = await source.vre_fraction_curve(grid_zone, hours)
                except Exception:
                    fetched = {}
                if fetched:
                    curve, method = fetched, label
                    break

        points: list[CarbonIntensity] = [current]
        for hour_offset in range(1, hours + 1):
            points.append(self._project_at(current, curve, hour_offset, longitude))

        # Stamp MEASURED marginal across the forecast where an operator-configured
        # source has it, so surplus/decisions use measured marginal -- not the
        # heuristic -- for future hours too. Best-effort; absent -> points stay heuristic.
        if self._marginal_source is not None and self._marginal_source.can_handle(grid_zone):
            try:
                mcurve = await self._marginal_source.marginal_forecast(grid_zone, hours)
            except Exception:
                mcurve = {}
            for h, point in enumerate(points):
                if h in mcurve:
                    point.marginal_intensity_gco2_kwh = mcurve[h]

        return method, points

    def _project_at(
        self,
        current: CarbonIntensity,
        curve: dict | None,
        hour_offset: int,
        longitude: float = 0.0,
    ) -> CarbonIntensity:
        """Project intensity at ``hour_offset``: the real forecast curve if available,
        else the local time-of-day model. Shared by find_optimal_window and forecast_zone."""
        projected: CarbonIntensity | None = None
        if curve and hour_offset in curve and 0 in curve:
            projected = self._project_with_forecast(
                current, curve[0], curve[hour_offset], hour_offset
            )
        if projected is None:
            projected = self._project_intensity(current, hour_offset, longitude)
        return projected

    def _project_with_forecast(
        self,
        current: CarbonIntensity,
        vre_now: float,
        vre_future: float,
        hours_ahead: int,
    ) -> CarbonIntensity | None:
        """Project intensity from a real day-ahead VRE-share forecast.

        Carbon comes from the non-VRE residual, so scaling current intensity by
        the change in residual share (1 - vre) gives a forecast-driven estimate:
        I(h) = I0 * (1 - vre_future) / (1 - vre_now). Returns None when the
        current zone is already ~100% VRE (no residual to scale).
        """
        if hours_ahead == 0:
            return current
        if vre_now >= 0.99:
            return None
        mult = (1 - vre_future) / (1 - vre_now)
        carbon = max(0.0, current.carbon_intensity_gco2_kwh * mult)
        renewable = min(
            100.0, max(0.0, current.renewable_percentage + (vre_future - vre_now) * 100)
        )
        return CarbonIntensity(
            grid_zone=current.grid_zone,
            carbon_intensity_gco2_kwh=round(carbon, 2),
            renewable_percentage=round(renewable, 1),
            timestamp=datetime.now(UTC) + timedelta(hours=hours_ahead),
            source=f"{current.source} (forecast +{hours_ahead}h)",
        )

    def _project_intensity(
        self, current: CarbonIntensity, hours_ahead: int, longitude: float = 0.0
    ) -> CarbonIntensity:
        """Project carbon intensity forward using a local time-of-day model.

        Still a heuristic, not a real grid forecast (that would need day-ahead
        operator forecasts / weather / ML). But it now anchors the solar/demand
        cycle to each region's *local* solar time, derived from longitude at 15°
        per hour, instead of UTC -- so midday solar and evening demand land at
        the right wall-clock hour for that region rather than being up to 12h off.
        """
        if hours_ahead == 0:
            return current

        now = datetime.now(UTC)
        # 15° of longitude == 1 hour offset from UTC -> approximate local hour.
        local_hour = (now.hour + hours_ahead + longitude / 15.0) % 24

        # Solar generation peaks midday local; demand peaks early evening local.
        solar_factor = self._solar_factor(local_hour)
        demand_factor = self._demand_factor(local_hour)

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
    def _solar_factor(hour: float) -> float:
        """Solar generation factor (0-1) by local hour. Peaks midday."""
        # Parabolic bell curve peaking at local noon.
        if 6 <= hour <= 18:
            return max(0, 1 - ((hour - 12) / 6) ** 2)
        return 0.0

    @staticmethod
    def _demand_factor(hour: float) -> float:
        """Electricity demand factor (0-1) by local hour. Peaks early evening."""
        if 7 <= hour <= 22:
            if 17 <= hour <= 20:
                return 1.0  # Evening peak
            elif 7 <= hour <= 9:
                return 0.7  # Morning ramp
            else:
                return 0.5  # Daytime baseline
        return 0.2  # Overnight low

    @staticmethod
    def _score_slot(
        intensity: CarbonIntensity, strategy: ScheduleStrategy, surplus: bool = False
    ) -> float:
        """Score a time slot. Lower = better for carbon strategies, higher for renewable.

        Clean-surplus slots get a bounded edge (see _SURPLUS_DISCOUNT): they're the
        highest-value time to add load, so they should win ties and close calls.
        """
        if strategy == ScheduleStrategy.LOWEST_CARBON:
            score = intensity.carbon_intensity_gco2_kwh
            return score * (1 - _SURPLUS_DISCOUNT) if surplus else score
        elif strategy == ScheduleStrategy.HIGHEST_RENEWABLE:
            # Higher = better, sorted descending; nudge surplus slots above equals.
            score = intensity.renewable_percentage
            return score + 5 if surplus else score
        else:
            # Balanced: weighted combination
            carbon_score = intensity.carbon_intensity_gco2_kwh / 500  # Normalize to 0-1
            renewable_score = 1 - (intensity.renewable_percentage / 100)  # Lower = more renewable
            score = carbon_score * 0.6 + renewable_score * 0.4
            return score * (1 - _SURPLUS_DISCOUNT) if surplus else score

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
