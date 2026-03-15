"""Tests for the compliance module — emissions calculation, reporting, usage ingestion."""

import pytest
from datetime import datetime, timezone

from carbon_mesh.models.compliance import (
    AccountingMethod,
    EmissionScope,
    PROVIDER_PUE,
    VCPU_HOUR_KWH,
)
from carbon_mesh.compliance.usage_ingestion import estimate_energy_kwh, MockUsageAdapter
from carbon_mesh.compliance.calculator import _scope_for_service, _data_quality
from carbon_mesh.compliance.reporting import ReportingEngine


# --- Energy estimation tests ---


def test_estimate_vcpu_hours_default():
    """Default vCPU-hour energy estimate uses CCF average."""
    kwh = estimate_energy_kwh(1000, "vcpu_hours", "unknown", "aws")
    pue = PROVIDER_PUE["aws"]
    expected = 1000 * VCPU_HOUR_KWH["default"] * pue
    assert abs(kwh - expected) < 0.001


def test_estimate_vcpu_hours_graviton():
    """Graviton (ARM) instances should use lower energy coefficient."""
    kwh_graviton = estimate_energy_kwh(1000, "vcpu_hours", "m6g.xlarge", "aws")
    kwh_default = estimate_energy_kwh(1000, "vcpu_hours", "m5.xlarge", "aws")
    assert kwh_graviton < kwh_default


def test_estimate_gb_hours():
    kwh = estimate_energy_kwh(100_000, "gb_hours", "ssd", "gcp")
    assert kwh > 0
    assert kwh < 1  # Storage is very low energy


def test_estimate_gb_transferred():
    kwh = estimate_energy_kwh(100, "gb_transferred", "default", "aws")
    assert kwh > 0


def test_estimate_requests():
    kwh = estimate_energy_kwh(1_000_000, "requests", "default", "gcp")
    assert kwh > 0


def test_estimate_unknown_unit():
    kwh = estimate_energy_kwh(100, "unknown_unit", "default", "aws")
    assert kwh == 0.0


def test_estimate_kwh_passthrough():
    kwh = estimate_energy_kwh(50, "kwh", "default", "aws")
    assert kwh == 50 * PROVIDER_PUE["aws"]


# --- Scope classification tests ---


def test_scope_compute_is_scope2():
    assert _scope_for_service("ec2") == EmissionScope.SCOPE_2
    assert _scope_for_service("compute-engine") == EmissionScope.SCOPE_2


def test_scope_managed_is_scope3():
    assert _scope_for_service("lambda") == EmissionScope.SCOPE_3_CAT1
    assert _scope_for_service("cloud-functions") == EmissionScope.SCOPE_3_CAT1
    assert _scope_for_service("dynamodb") == EmissionScope.SCOPE_3_CAT1


# --- Data quality tests ---


def test_data_quality_measured():
    assert _data_quality("uk") == "measured"
    assert _data_quality("eia") == "measured"
    assert _data_quality("entsoe") == "measured"


def test_data_quality_modeled():
    assert _data_quality("open_meteo") == "modeled"


def test_data_quality_default():
    assert _data_quality("mock") == "default"


# --- Mock usage adapter ---


@pytest.mark.asyncio
async def test_mock_usage_adapter():
    adapter = MockUsageAdapter()
    records = await adapter.fetch_usage(
        org_id="test-org",
        period_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        period_end=datetime(2024, 1, 31, tzinfo=timezone.utc),
    )
    assert len(records) == 10  # 10 demo records
    assert all(r.org_id == "test-org" for r in records)
    assert all(r.energy_kwh > 0 for r in records)
    providers = {r.provider for r in records}
    assert providers == {"aws", "gcp", "azure"}


# --- Reporting engine ---


def test_empty_report():
    engine = ReportingEngine()
    report = engine.generate_report("org1", "Test Org", [])
    assert report.total_kgco2e == 0
    assert report.calculation_count == 0


def test_report_with_calculations():
    from carbon_mesh.models.compliance import EmissionsCalculation

    now = datetime.now(timezone.utc)
    calcs = [
        EmissionsCalculation(
            id="calc-1",
            org_id="org1",
            scope=EmissionScope.SCOPE_2,
            method=AccountingMethod.LOCATION_BASED,
            provider="aws",
            region="us-east-1",
            grid_zone="US-MIDA-PJM",
            service="ec2",
            resource_type="m6i.xlarge",
            usage_quantity=1000,
            usage_unit="vcpu_hours",
            energy_kwh=3.5,
            emission_factor_gco2_kwh=350,
            emission_factor_source="eia",
            emission_factor_quality="measured",
            emissions_kgco2e=1.225,
            renewable_percentage=30,
            pue=1.135,
            period_start=now,
            period_end=now,
            calculated_at=now,
        ),
        EmissionsCalculation(
            id="calc-2",
            org_id="org1",
            scope=EmissionScope.SCOPE_3_CAT1,
            method=AccountingMethod.LOCATION_BASED,
            provider="gcp",
            region="us-central1",
            grid_zone="US-MIDW-MISO",
            service="cloud-functions",
            resource_type="default",
            usage_quantity=2_000_000,
            usage_unit="requests",
            energy_kwh=0.4,
            emission_factor_gco2_kwh=400,
            emission_factor_source="eia",
            emission_factor_quality="measured",
            emissions_kgco2e=0.16,
            renewable_percentage=25,
            pue=1.10,
            period_start=now,
            period_end=now,
            calculated_at=now,
        ),
    ]

    engine = ReportingEngine()
    report = engine.generate_report("org1", "Test Org", calcs)

    assert report.scope2_location_kgco2e == 1.225
    assert report.scope3_cat1_kgco2e == 0.16
    assert report.total_kgco2e == pytest.approx(1.385, rel=0.01)
    assert report.total_providers_used == 2
    assert report.total_cloud_regions_used == 2
    assert report.calculation_count == 2
    assert report.reporting_standard == "CSRD / ESRS E1"
    assert "eia" in report.data_sources
    assert report.data_quality_summary["measured"] == 2
    assert report.carbon_saved_percentage > 0


def test_report_summary():
    from carbon_mesh.models.compliance import EmissionsCalculation

    now = datetime.now(timezone.utc)
    calcs = [
        EmissionsCalculation(
            id="c1",
            org_id="org1",
            scope=EmissionScope.SCOPE_2,
            method=AccountingMethod.LOCATION_BASED,
            provider="aws",
            region="eu-west-1",
            grid_zone="IE",
            service="ec2",
            resource_type="default",
            usage_quantity=100,
            usage_unit="vcpu_hours",
            energy_kwh=0.35,
            emission_factor_gco2_kwh=300,
            emission_factor_source="entsoe",
            emission_factor_quality="measured",
            emissions_kgco2e=0.105,
            renewable_percentage=45,
            pue=1.135,
            period_start=now,
            period_end=now,
            calculated_at=now,
        ),
    ]

    engine = ReportingEngine()
    report = engine.generate_report("org1", "Test Org", calcs)
    summary = engine.summarize(report)

    assert summary.id == report.id
    assert summary.total_kgco2e == report.total_kgco2e
    assert summary.total_energy_kwh == report.total_energy_kwh
