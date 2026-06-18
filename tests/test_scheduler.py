"""Tests for carbon-aware scheduling — engine, models, and routes."""

import uuid
from datetime import datetime, timezone

import pytest

from carbon_mesh.models.carbon import CarbonIntensity
from carbon_mesh.scheduler.engine import (
    CronSchedule,
    ScheduleRecommendation,
    ScheduleStrategy,
    SchedulingEngine,
    TimeSlot,
)


# --- Fixtures ---


class MockCarbonSource:
    """Mock carbon source returning configurable per-zone data."""

    def __init__(
        self,
        default_intensity: float = 200.0,
        default_renewable: float = 45.0,
        zone_overrides: dict[str, tuple[float, float]] | None = None,
    ):
        self._default_intensity = default_intensity
        self._default_renewable = default_renewable
        self._overrides = zone_overrides or {}

    async def get_carbon_intensity(self, grid_zone: str) -> CarbonIntensity:
        intensity, renewable = self._overrides.get(
            grid_zone, (self._default_intensity, self._default_renewable)
        )
        return CarbonIntensity(
            grid_zone=grid_zone,
            carbon_intensity_gco2_kwh=intensity,
            renewable_percentage=renewable,
            timestamp=datetime.now(timezone.utc),
            source="mock",
        )

    async def get_carbon_intensity_batch(self, grid_zones: list[str]):
        return {z: await self.get_carbon_intensity(z) for z in grid_zones}


class MockGridMapper:
    """Mock grid mapper with a few test regions."""

    def __init__(self):
        self._regions = {
            ("aws", "us-east-1"): "US-MIDA-PJM",
            ("aws", "eu-west-1"): "IE",
            ("gcp", "europe-north1"): "FI",
            ("gcp", "us-central1"): "US-MIDW-MISO",
            ("azure", "westeurope"): "NL",
        }

    def get_grid_zone(self, provider: str, region: str) -> str | None:
        return self._regions.get((provider, region))

    def get_region(self, provider: str, region: str):
        from carbon_mesh.models.region import CloudRegion

        zone = self._regions.get((provider, region))
        if zone is None:
            return None
        return CloudRegion(
            provider=provider,
            region=region,
            grid_zone=zone,
            location="Test",
            latitude=0,
            longitude=0,
        )

    def list_regions(self, provider: str | None = None):
        from carbon_mesh.models.region import CloudRegion

        regions = []
        for (prov, reg), zone in self._regions.items():
            if provider and prov != provider:
                continue
            regions.append(
                CloudRegion(
                    provider=prov,
                    region=reg,
                    grid_zone=zone,
                    location="Test",
                    latitude=0,
                    longitude=0,
                )
            )
        return regions


# --- Model tests ---


def test_schedule_strategy_enum():
    assert ScheduleStrategy.LOWEST_CARBON.value == "lowest_carbon"
    assert ScheduleStrategy.HIGHEST_RENEWABLE.value == "highest_renewable"
    assert ScheduleStrategy.BALANCED.value == "balanced"


def test_time_slot_model():
    slot = TimeSlot(
        start=datetime.now(timezone.utc),
        end=datetime.now(timezone.utc),
        provider="aws",
        region="us-east-1",
        grid_zone="US-MIDA-PJM",
        carbon_intensity_gco2_kwh=150.0,
        renewable_percentage=40.0,
        score=150.0,
    )
    assert slot.provider == "aws"
    assert slot.carbon_intensity_gco2_kwh == 150.0


def test_cron_schedule_model():
    schedule = CronSchedule(
        id=str(uuid.uuid4()),
        name="Nightly ETL",
        org_id="test-org",
        job_duration_minutes=60,
        providers=["aws", "gcp"],
        strategy=ScheduleStrategy.BALANCED,
        max_delay_hours=12,
        created_at=datetime.now(timezone.utc),
    )
    assert schedule.name == "Nightly ETL"
    assert schedule.active is True
    assert schedule.strategy == ScheduleStrategy.BALANCED


def test_schedule_recommendation_model():
    now = datetime.now(timezone.utc)
    slot = TimeSlot(
        start=now,
        end=now,
        provider="gcp",
        region="europe-north1",
        grid_zone="FI",
        carbon_intensity_gco2_kwh=30.0,
        renewable_percentage=90.0,
        score=30.0,
    )
    rec = ScheduleRecommendation(
        id=str(uuid.uuid4()),
        recommended=slot,
        alternatives=[],
        job_duration_minutes=30,
        window_start=now,
        window_end=now,
        strategy=ScheduleStrategy.LOWEST_CARBON,
        carbon_saved_vs_now_pct=45.0,
        evaluated_slots=24,
    )
    assert rec.carbon_saved_vs_now_pct == 45.0
    assert rec.evaluated_slots == 24


# --- Engine tests ---


@pytest.mark.asyncio
async def test_find_optimal_window_returns_recommendation():
    """Engine should return a valid recommendation."""
    source = MockCarbonSource()
    mapper = MockGridMapper()
    engine = SchedulingEngine(carbon_source=source, grid_mapper=mapper)

    rec = await engine.find_optimal_window(
        job_duration_minutes=30,
        providers=["aws", "gcp"],
    )

    assert isinstance(rec, ScheduleRecommendation)
    assert rec.recommended is not None
    assert rec.evaluated_slots > 0
    assert rec.job_duration_minutes == 30


@pytest.mark.asyncio
async def test_forecast_zone_stamps_measured_marginal():
    """When a marginal source has a forecast for the zone, forecast points carry the
    measured marginal instead of the heuristic/None."""

    class FakeMarginal:
        def can_handle(self, zone):
            return zone == "FI"

        async def marginal_forecast(self, zone, hours):
            return {0: 111.0, 1: 99.0}

    engine = SchedulingEngine(
        carbon_source=MockCarbonSource(),
        grid_mapper=MockGridMapper(),
        marginal_source=FakeMarginal(),
    )
    _, points = await engine.forecast_zone("FI", longitude=0.0, hours=3)
    assert points[0].marginal_intensity_gco2_kwh == 111.0
    assert points[1].marginal_intensity_gco2_kwh == 99.0


@pytest.mark.asyncio
async def test_long_job_is_scored_over_its_whole_window():
    """A multi-hour job's slot intensity is the average over its run window, not just
    the start hour."""
    source = MockCarbonSource(default_intensity=300, default_renewable=30)
    engine = SchedulingEngine(carbon_source=source, grid_mapper=MockGridMapper())

    rec = await engine.find_optimal_window(
        job_duration_minutes=180,  # 3 hours
        providers=["gcp"],
        preferred_regions=["europe-north1"],
        max_delay_hours=12,
    )

    current = await source.get_carbon_intensity("FI")
    expected = round(
        sum(engine._project_intensity(current, h, 0.0).carbon_intensity_gco2_kwh for h in range(3))
        / 3,
        2,
    )
    slot0 = next(s for s in rec.forecast if s.start == rec.window_start)
    assert slot0.carbon_intensity_gco2_kwh == expected


@pytest.mark.asyncio
async def test_find_optimal_window_lowest_carbon():
    """Lowest-carbon strategy should pick the zone with lowest intensity."""
    source = MockCarbonSource(
        zone_overrides={
            "FI": (20.0, 90.0),  # Very green
            "US-MIDA-PJM": (400.0, 15.0),  # Very dirty
            "IE": (150.0, 55.0),
        }
    )
    mapper = MockGridMapper()
    engine = SchedulingEngine(carbon_source=source, grid_mapper=mapper)

    rec = await engine.find_optimal_window(
        job_duration_minutes=30,
        providers=["aws", "gcp"],
        strategy=ScheduleStrategy.LOWEST_CARBON,
        max_delay_hours=1,
    )

    # Finland (FI) has the lowest carbon — should be recommended
    assert rec.recommended.grid_zone == "FI"
    assert rec.recommended.carbon_intensity_gco2_kwh == 20.0


@pytest.mark.asyncio
async def test_find_optimal_window_highest_renewable():
    """Highest-renewable strategy should pick the zone with most renewables."""
    source = MockCarbonSource(
        zone_overrides={
            "FI": (50.0, 95.0),  # Highest renewable
            "US-MIDA-PJM": (200.0, 30.0),
            "IE": (100.0, 60.0),
        }
    )
    mapper = MockGridMapper()
    engine = SchedulingEngine(carbon_source=source, grid_mapper=mapper)

    rec = await engine.find_optimal_window(
        job_duration_minutes=30,
        providers=["aws", "gcp"],
        strategy=ScheduleStrategy.HIGHEST_RENEWABLE,
        max_delay_hours=1,
    )

    assert rec.recommended.grid_zone == "FI"
    assert rec.recommended.renewable_percentage == 95.0


@pytest.mark.asyncio
async def test_find_optimal_window_preferred_regions():
    """Preferred regions should constrain the search."""
    source = MockCarbonSource(
        zone_overrides={
            "US-MIDA-PJM": (300.0, 20.0),
            "IE": (100.0, 60.0),
        }
    )
    mapper = MockGridMapper()
    engine = SchedulingEngine(carbon_source=source, grid_mapper=mapper)

    rec = await engine.find_optimal_window(
        job_duration_minutes=30,
        providers=["aws"],
        preferred_regions=["us-east-1", "eu-west-1"],
        max_delay_hours=1,
    )

    # Should only check AWS regions in preferred list
    all_zones = {rec.recommended.grid_zone} | {a.grid_zone for a in rec.alternatives}
    assert all_zones <= {"US-MIDA-PJM", "IE"}


@pytest.mark.asyncio
async def test_find_optimal_window_single_provider():
    """Single provider should only evaluate that provider's regions."""
    source = MockCarbonSource()
    mapper = MockGridMapper()
    engine = SchedulingEngine(carbon_source=source, grid_mapper=mapper)

    rec = await engine.find_optimal_window(
        job_duration_minutes=30,
        providers=["azure"],
        max_delay_hours=1,
    )

    assert rec.recommended.provider == "azure"


@pytest.mark.asyncio
async def test_find_optimal_window_no_valid_regions():
    """Nonexistent provider should still return a fallback."""
    source = MockCarbonSource()
    mapper = MockGridMapper()
    engine = SchedulingEngine(carbon_source=source, grid_mapper=mapper)

    rec = await engine.find_optimal_window(
        job_duration_minutes=30,
        providers=["nonexistent"],
        max_delay_hours=1,
    )

    # Should return a fallback recommendation
    assert rec.evaluated_slots == 0


@pytest.mark.asyncio
async def test_find_optimal_window_carbon_savings():
    """Should compute carbon savings vs worst-now option."""
    source = MockCarbonSource(
        zone_overrides={
            "FI": (20.0, 95.0),
            "US-MIDA-PJM": (400.0, 15.0),
            "IE": (200.0, 50.0),
            "US-MIDW-MISO": (300.0, 30.0),
        }
    )
    mapper = MockGridMapper()
    engine = SchedulingEngine(carbon_source=source, grid_mapper=mapper)

    rec = await engine.find_optimal_window(
        job_duration_minutes=30,
        providers=["aws", "gcp"],
        max_delay_hours=1,
    )

    assert rec.carbon_saved_vs_now_pct > 0


@pytest.mark.asyncio
async def test_find_optimal_window_multi_hour():
    """Multi-hour window should produce more time slots."""
    source = MockCarbonSource()
    mapper = MockGridMapper()
    engine = SchedulingEngine(carbon_source=source, grid_mapper=mapper)

    rec_1h = await engine.find_optimal_window(
        job_duration_minutes=30,
        providers=["aws", "gcp"],
        max_delay_hours=1,
    )
    rec_24h = await engine.find_optimal_window(
        job_duration_minutes=30,
        providers=["aws", "gcp"],
        max_delay_hours=24,
    )

    assert rec_24h.evaluated_slots >= rec_1h.evaluated_slots


# --- Heuristic helper tests ---


def test_solar_factor():
    """Solar factor should peak at midday, zero at night."""
    assert SchedulingEngine._solar_factor(12) > 0.9  # Noon peak
    assert SchedulingEngine._solar_factor(0) == 0.0  # Midnight
    assert SchedulingEngine._solar_factor(3) == 0.0  # Early morning
    assert SchedulingEngine._solar_factor(9) > 0  # Morning


def test_demand_factor():
    """Demand factor should peak in evening, low overnight."""
    assert SchedulingEngine._demand_factor(18) == 1.0  # Evening peak
    assert SchedulingEngine._demand_factor(3) == 0.2  # Overnight low
    assert SchedulingEngine._demand_factor(8) == 0.7  # Morning ramp


def test_score_slot_lowest_carbon():
    """Score for lowest-carbon should equal carbon intensity."""
    intensity = CarbonIntensity(
        grid_zone="test",
        carbon_intensity_gco2_kwh=150.0,
        renewable_percentage=50.0,
        timestamp=datetime.now(timezone.utc),
        source="test",
    )
    score = SchedulingEngine._score_slot(intensity, ScheduleStrategy.LOWEST_CARBON)
    assert score == 150.0


def test_score_slot_highest_renewable():
    """Score for highest-renewable should equal renewable percentage."""
    intensity = CarbonIntensity(
        grid_zone="test",
        carbon_intensity_gco2_kwh=150.0,
        renewable_percentage=80.0,
        timestamp=datetime.now(timezone.utc),
        source="test",
    )
    score = SchedulingEngine._score_slot(intensity, ScheduleStrategy.HIGHEST_RENEWABLE)
    assert score == 80.0


def test_score_slot_balanced():
    """Balanced score should be a weighted combination."""
    intensity = CarbonIntensity(
        grid_zone="test",
        carbon_intensity_gco2_kwh=250.0,
        renewable_percentage=50.0,
        timestamp=datetime.now(timezone.utc),
        source="test",
    )
    score = SchedulingEngine._score_slot(intensity, ScheduleStrategy.BALANCED)
    # carbon_score = 250/500 = 0.5, renewable_score = 1 - 50/100 = 0.5
    # balanced = 0.5 * 0.6 + 0.5 * 0.4 = 0.5
    assert score == pytest.approx(0.5)


def test_score_slot_surplus_gets_bounded_edge():
    """A clean-surplus slot ranks ahead of a close non-surplus one, but a much
    cleaner non-surplus slot still wins -- the edge is bounded."""

    def slot(carbon, renewable):
        return CarbonIntensity(
            grid_zone="test",
            carbon_intensity_gco2_kwh=carbon,
            renewable_percentage=renewable,
            timestamp=datetime.now(timezone.utc),
            source="test",
        )

    # Surplus slot at 80 scores as if ~48 (40% off) -> beats a non-surplus 60...
    surplus_80 = SchedulingEngine._score_slot(slot(80, 95), ScheduleStrategy.LOWEST_CARBON, True)
    non_surplus_60 = SchedulingEngine._score_slot(slot(60, 50), ScheduleStrategy.LOWEST_CARBON)
    assert surplus_80 < non_surplus_60
    # ...but does NOT beat a genuinely much cleaner non-surplus slot at 30.
    non_surplus_30 = SchedulingEngine._score_slot(slot(30, 70), ScheduleStrategy.LOWEST_CARBON)
    assert surplus_80 > non_surplus_30
