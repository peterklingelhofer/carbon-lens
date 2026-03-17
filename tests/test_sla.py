"""Tests for Green SLA monitoring — engine, monitor, and models."""

import asyncio
import uuid
from datetime import datetime, timezone, timedelta

import pytest

from carbon_mesh.models.sla import (
    AlertChannel,
    GreenSLA,
    SLACheck,
    SLACheckFrequency,
    SLAReport,
    SLAStatus,
    SLASummary,
    AlertEvent,
)
from carbon_mesh.sla.engine import SLAEngine
from carbon_mesh.sla.monitor import SLAMonitor, FREQUENCY_SECONDS


# --- Fixtures ---

class MockCarbonSource:
    """Mock carbon source that returns predictable data."""

    def __init__(self, intensity: float = 200.0, renewable: float = 45.0):
        self._intensity = intensity
        self._renewable = renewable

    async def get_carbon_intensity(self, grid_zone: str):
        from carbon_mesh.models.carbon import CarbonIntensity
        return CarbonIntensity(
            grid_zone=grid_zone,
            carbon_intensity_gco2_kwh=self._intensity,
            renewable_percentage=self._renewable,
            timestamp=datetime.now(timezone.utc),
            source="mock",
        )

    async def get_carbon_intensity_batch(self, grid_zones: list[str]):
        results = {}
        for zone in grid_zones:
            results[zone] = await self.get_carbon_intensity(zone)
        return results


class MockGridMapper:
    """Mock grid mapper with a few test regions."""

    def __init__(self):
        self._regions = {
            ("aws", "us-east-1"): "US-MIDA-PJM",
            ("aws", "eu-west-1"): "IE",
            ("gcp", "europe-north1"): "FI",
            ("gcp", "us-central1"): "US-MIDW-MISO",
        }

    def get_grid_zone(self, provider: str, region: str) -> str | None:
        return self._regions.get((provider, region))

    def list_regions(self, provider: str | None = None):
        from carbon_mesh.models.region import CloudRegion
        regions = []
        for (prov, reg), zone in self._regions.items():
            if provider and prov != provider:
                continue
            regions.append(CloudRegion(
                provider=prov,
                region=reg,
                grid_zone=zone,
                location="Test",
                latitude=0,
                longitude=0,
            ))
        return regions


def _make_sla(**kwargs) -> GreenSLA:
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=str(uuid.uuid4()),
        org_id="test-org",
        name="Test SLA",
        max_carbon_intensity_gco2_kwh=100.0,
        min_renewable_percentage=50.0,
        providers=["aws", "gcp"],
        regions=[],
        check_frequency=SLACheckFrequency.HOURLY,
        alert_channels=[],
        webhook_url="",
        created_at=now,
        updated_at=now,
    )
    defaults.update(kwargs)
    return GreenSLA(**defaults)


# --- Model tests ---

def test_sla_model_creation():
    sla = _make_sla()
    assert sla.name == "Test SLA"
    assert sla.max_carbon_intensity_gco2_kwh == 100.0
    assert sla.active is True


def test_sla_check_model():
    check = SLACheck(
        id="check-1",
        sla_id="sla-1",
        checked_at=datetime.now(timezone.utc),
        status=SLAStatus.COMPLIANT,
        avg_carbon_intensity_gco2_kwh=50.0,
        max_carbon_intensity_gco2_kwh=80.0,
        min_carbon_intensity_gco2_kwh=20.0,
        avg_renewable_percentage=75.0,
        regions_checked=10,
        regions_compliant=10,
        regions_breached=0,
        breached_regions=[],
        target_max_carbon=100.0,
        target_min_renewable=50.0,
    )
    assert check.status == SLAStatus.COMPLIANT
    assert check.regions_breached == 0


def test_sla_status_enum():
    assert SLAStatus.COMPLIANT.value == "compliant"
    assert SLAStatus.BREACHED.value == "breached"
    assert SLAStatus.WARNING.value == "warning"


def test_sla_summary_model():
    summary = SLASummary(
        id="sla-1",
        name="Prod SLA",
        org_id="org-1",
        status=SLAStatus.COMPLIANT,
        max_carbon_intensity_gco2_kwh=100.0,
        min_renewable_percentage=50.0,
        check_frequency=SLACheckFrequency.DAILY,
        last_checked=datetime.now(timezone.utc),
        active=True,
    )
    assert summary.name == "Prod SLA"
    assert summary.active is True


def test_alert_event_model():
    event = AlertEvent(
        id="alert-1",
        sla_id="sla-1",
        sla_name="Test SLA",
        channel=AlertChannel.WEBHOOK,
        sent_at=datetime.now(timezone.utc),
        status=SLAStatus.BREACHED,
        details={"regions_breached": 3},
        delivery_status="sent",
    )
    assert event.channel == AlertChannel.WEBHOOK
    assert event.delivery_status == "sent"


def test_sla_report_model():
    report = SLAReport(
        id="report-1",
        sla_id="sla-1",
        org_id="org-1",
        org_name="Test Org",
        sla_name="Test SLA",
        period_start=datetime.now(timezone.utc) - timedelta(days=30),
        period_end=datetime.now(timezone.utc),
        generated_at=datetime.now(timezone.utc),
        total_checks=100,
        compliant_checks=95,
        warning_checks=3,
        breached_checks=2,
        compliance_percentage=95.0,
        avg_carbon_intensity_gco2_kwh=75.0,
        max_carbon_intensity_gco2_kwh=350.0,
        avg_renewable_percentage=60.0,
        min_renewable_percentage=30.0,
        target_max_carbon=100.0,
        target_min_renewable=50.0,
    )
    assert report.compliance_percentage == 95.0
    assert report.breached_checks == 2


def test_frequency_seconds():
    assert FREQUENCY_SECONDS[SLACheckFrequency.HOURLY] == 3600
    assert FREQUENCY_SECONDS[SLACheckFrequency.DAILY] == 86400
    assert FREQUENCY_SECONDS[SLACheckFrequency.WEEKLY] == 604800


# --- Engine tests ---

@pytest.mark.asyncio
async def test_check_sla_compliant():
    """SLA check should be compliant when carbon is below threshold."""
    source = MockCarbonSource(intensity=50.0, renewable=80.0)
    mapper = MockGridMapper()
    engine = SLAEngine(carbon_source=source, grid_mapper=mapper)

    sla = _make_sla(max_carbon_intensity_gco2_kwh=100.0, min_renewable_percentage=50.0)
    check = await engine.check_sla(sla)

    assert check.status == SLAStatus.COMPLIANT
    assert check.regions_breached == 0
    assert check.avg_carbon_intensity_gco2_kwh == 50.0
    assert check.avg_renewable_percentage == 80.0


@pytest.mark.asyncio
async def test_check_sla_breached():
    """SLA check should be breached when carbon exceeds threshold."""
    source = MockCarbonSource(intensity=300.0, renewable=20.0)
    mapper = MockGridMapper()
    engine = SLAEngine(carbon_source=source, grid_mapper=mapper)

    sla = _make_sla(max_carbon_intensity_gco2_kwh=100.0, min_renewable_percentage=50.0)
    check = await engine.check_sla(sla)

    assert check.status == SLAStatus.BREACHED
    assert check.regions_breached > 0
    assert len(check.breached_regions) > 0


@pytest.mark.asyncio
async def test_check_sla_with_specific_regions():
    """SLA check should only check specified regions."""
    source = MockCarbonSource(intensity=50.0, renewable=80.0)
    mapper = MockGridMapper()
    engine = SLAEngine(carbon_source=source, grid_mapper=mapper)

    sla = _make_sla(regions=["us-east-1"])
    check = await engine.check_sla(sla)

    # Should only check regions that exist in the mapper
    assert check.regions_checked >= 1


@pytest.mark.asyncio
async def test_check_sla_no_regions():
    """SLA check with empty providers should return unknown."""
    source = MockCarbonSource()
    mapper = MockGridMapper()
    engine = SLAEngine(carbon_source=source, grid_mapper=mapper)

    sla = _make_sla(providers=["nonexistent_provider"])
    check = await engine.check_sla(sla)

    assert check.status == SLAStatus.UNKNOWN
    assert check.regions_checked == 0


@pytest.mark.asyncio
async def test_check_sla_renewable_breach_only():
    """SLA should breach if renewable % is too low even if carbon is OK."""
    source = MockCarbonSource(intensity=50.0, renewable=30.0)
    mapper = MockGridMapper()
    engine = SLAEngine(carbon_source=source, grid_mapper=mapper)

    sla = _make_sla(max_carbon_intensity_gco2_kwh=100.0, min_renewable_percentage=50.0)
    check = await engine.check_sla(sla)

    assert check.status == SLAStatus.BREACHED
    for region in check.breached_regions:
        assert region["renewable_breached"] is True


@pytest.mark.asyncio
async def test_generate_report_from_checks():
    """Report generation should aggregate checks correctly."""
    source = MockCarbonSource(intensity=50.0, renewable=80.0)
    mapper = MockGridMapper()
    engine = SLAEngine(carbon_source=source, grid_mapper=mapper)

    sla = _make_sla()
    now = datetime.now(timezone.utc)

    # Create some mock checks
    checks = []
    for i in range(5):
        check = SLACheck(
            id=str(uuid.uuid4()),
            sla_id=sla.id,
            checked_at=now - timedelta(hours=i),
            status=SLAStatus.COMPLIANT if i < 4 else SLAStatus.BREACHED,
            avg_carbon_intensity_gco2_kwh=50.0 + i * 10,
            max_carbon_intensity_gco2_kwh=80.0 + i * 10,
            min_carbon_intensity_gco2_kwh=20.0,
            avg_renewable_percentage=80.0 - i * 5,
            regions_checked=4,
            regions_compliant=4 if i < 4 else 2,
            regions_breached=0 if i < 4 else 2,
            breached_regions=[] if i < 4 else [
                {"provider": "aws", "region": "us-east-1", "grid_zone": "US-MIDA-PJM",
                 "carbon_intensity_gco2_kwh": 120.0, "renewable_breached": False,
                 "carbon_breached": True, "renewable_percentage": 60.0},
            ],
            target_max_carbon=100.0,
            target_min_renewable=50.0,
        )
        checks.append(check)

    report = engine.generate_report(
        sla=sla,
        checks=checks,
        org_name="Test Org",
        period_start=now - timedelta(days=1),
        period_end=now,
    )

    assert report.total_checks == 5
    assert report.compliant_checks == 4
    assert report.breached_checks == 1
    assert report.compliance_percentage == 80.0
    assert len(report.checks_by_day) >= 1


@pytest.mark.asyncio
async def test_generate_report_empty_checks():
    """Report generation with no checks should return zeros."""
    source = MockCarbonSource()
    mapper = MockGridMapper()
    engine = SLAEngine(carbon_source=source, grid_mapper=mapper)

    sla = _make_sla()
    now = datetime.now(timezone.utc)

    report = engine.generate_report(
        sla=sla,
        checks=[],
        org_name="Test Org",
        period_start=now - timedelta(days=30),
        period_end=now,
    )

    assert report.total_checks == 0
    assert report.compliance_percentage == 0


def test_summarize_sla():
    """SLA summary should reflect last check status."""
    source = MockCarbonSource()
    mapper = MockGridMapper()
    engine = SLAEngine(carbon_source=source, grid_mapper=mapper)

    sla = _make_sla()
    check = SLACheck(
        id="check-1",
        sla_id=sla.id,
        checked_at=datetime.now(timezone.utc),
        status=SLAStatus.WARNING,
        avg_carbon_intensity_gco2_kwh=90.0,
        max_carbon_intensity_gco2_kwh=110.0,
        min_carbon_intensity_gco2_kwh=50.0,
        avg_renewable_percentage=55.0,
        regions_checked=4,
        regions_compliant=3,
        regions_breached=1,
        breached_regions=[],
        target_max_carbon=100.0,
        target_min_renewable=50.0,
    )

    summary = engine.summarize(sla, check)
    assert summary.status == SLAStatus.WARNING
    assert summary.name == sla.name


def test_summarize_sla_no_checks():
    """SLA summary with no checks should show unknown status."""
    source = MockCarbonSource()
    mapper = MockGridMapper()
    engine = SLAEngine(carbon_source=source, grid_mapper=mapper)

    sla = _make_sla()
    summary = engine.summarize(sla, None)
    assert summary.status == SLAStatus.UNKNOWN


# --- Monitor tests ---

@pytest.mark.asyncio
async def test_monitor_status_when_stopped():
    source = MockCarbonSource()
    mapper = MockGridMapper()
    engine = SLAEngine(carbon_source=source, grid_mapper=mapper)
    monitor = SLAMonitor(engine=engine)

    status = monitor.get_status()
    assert status["running"] is False
    assert status["checks_completed"] == 0


@pytest.mark.asyncio
async def test_monitor_start_stop():
    source = MockCarbonSource()
    mapper = MockGridMapper()
    engine = SLAEngine(carbon_source=source, grid_mapper=mapper)
    monitor = SLAMonitor(engine=engine)

    sla = _make_sla()
    await monitor.start([sla])
    assert monitor.running is True

    await monitor.stop()
    assert monitor.running is False


@pytest.mark.asyncio
async def test_monitor_alerts_empty():
    source = MockCarbonSource()
    mapper = MockGridMapper()
    engine = SLAEngine(carbon_source=source, grid_mapper=mapper)
    monitor = SLAMonitor(engine=engine)

    alerts = monitor.get_recent_alerts()
    assert alerts == []
