"""Compliance API endpoints — usage ingestion, emissions calculation, report generation."""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from pydantic import BaseModel

from carbon_mesh.api.deps import get_carbon_source, get_grid_mapper
from carbon_mesh.auth.dependencies import require_api_key
from carbon_mesh.compliance.calculator import EmissionsCalculator
from carbon_mesh.compliance.reporting import ReportingEngine
from carbon_mesh.compliance.usage_ingestion import (
    CloudIngestionError,
    ManualCSVAdapter,
    MockUsageAdapter,
)
from carbon_mesh.models.compliance import (
    AccountingMethod,
    CloudUsageRecord,
    ComplianceReport,
    ComplianceReportSummary,
    EmissionsCalculation,
)

logger = logging.getLogger(__name__)
router = APIRouter(
    prefix="/api/v1/compliance",
    tags=["Compliance"],
    dependencies=[Depends(require_api_key)],
)

# In-memory store for MVP (DB persistence when use_database=True)
_usage_store: dict[str, list[CloudUsageRecord]] = {}  # org_id -> records
_calculation_store: dict[str, list[EmissionsCalculation]] = {}  # org_id -> calculations
_report_store: dict[str, list[ComplianceReport]] = {}  # org_id -> reports


# --- Request/response models ---


class UsageIngestionRequest(BaseModel):
    org_id: str
    provider: str  # "aws", "gcp", "azure", "manual", "mock"
    period_start: datetime
    period_end: datetime
    credentials: dict[str, str] | None = None


class CalculateRequest(BaseModel):
    org_id: str
    method: AccountingMethod = AccountingMethod.LOCATION_BASED


class GenerateReportRequest(BaseModel):
    org_id: str
    org_name: str
    report_name: str = ""
    period_start: datetime | None = None
    period_end: datetime | None = None


class UsageIngestionResponse(BaseModel):
    records_ingested: int
    total_energy_kwh: float
    providers_covered: list[str]
    regions_covered: list[str]


class CalculationResponse(BaseModel):
    calculations_count: int
    total_emissions_kgco2e: float
    scope2_kgco2e: float
    scope3_kgco2e: float
    data_sources_used: list[str]


# --- Endpoints ---


@router.post("/usage/ingest", response_model=UsageIngestionResponse)
async def ingest_usage(req: UsageIngestionRequest) -> UsageIngestionResponse:
    """Ingest cloud usage data from a provider or mock data for demo."""
    if req.provider == "mock":
        adapter = MockUsageAdapter()
    elif req.provider == "manual":
        raise HTTPException(400, "Use /usage/upload-csv for manual CSV ingestion")
    else:
        # For real providers, check for credentials
        if not req.credentials:
            raise HTTPException(
                400,
                f"Credentials required for {req.provider}. "
                "Provide aws_access_key_id/aws_secret_access_key for AWS, "
                "project_id/billing_dataset for GCP, or "
                "tenant_id/client_id/client_secret/subscription_id for Azure.",
            )
        # Lazy-import real adapters
        if req.provider == "aws":
            from carbon_mesh.compliance.usage_ingestion import AWSCostExplorerAdapter

            adapter = AWSCostExplorerAdapter()
        elif req.provider == "gcp":
            from carbon_mesh.compliance.usage_ingestion import GCPBillingAdapter

            adapter = GCPBillingAdapter()
        elif req.provider == "azure":
            from carbon_mesh.compliance.usage_ingestion import AzureCostManagementAdapter

            adapter = AzureCostManagementAdapter()
        else:
            raise HTTPException(400, f"Unknown provider: {req.provider}")

    try:
        records = await adapter.fetch_usage(
            org_id=req.org_id,
            period_start=req.period_start,
            period_end=req.period_end,
            credentials=req.credentials,
        )
    except CloudIngestionError as e:
        # Missing SDK (cloud extra) or upstream credential/permission/API failure.
        raise HTTPException(status_code=502, detail=str(e)) from e

    # Store
    if req.org_id not in _usage_store:
        _usage_store[req.org_id] = []
    _usage_store[req.org_id].extend(records)

    providers = sorted({r.provider for r in records})
    regions = sorted({f"{r.provider}/{r.region}" for r in records})
    total_energy = sum(r.energy_kwh for r in records)

    return UsageIngestionResponse(
        records_ingested=len(records),
        total_energy_kwh=round(total_energy, 4),
        providers_covered=providers,
        regions_covered=regions,
    )


@router.post("/usage/upload-csv", response_model=UsageIngestionResponse)
async def upload_csv(
    org_id: str = Query(...),
    file: UploadFile = File(...),
) -> UsageIngestionResponse:
    """Upload a CSV file with cloud usage data."""
    content = await file.read()
    try:
        csv_text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(400, "File must be a UTF-8 encoded CSV.") from exc

    adapter = ManualCSVAdapter()
    try:
        records = await adapter.fetch_usage(
            org_id=org_id,
            period_start=datetime.min,
            period_end=datetime.max,
            csv_content=csv_text,
        )
    except (KeyError, ValueError) as exc:
        raise HTTPException(
            400,
            "Could not parse the CSV. Required columns: provider, region, service, "
            "usage_quantity, usage_unit, period_start, period_end (ISO dates); "
            f"resource_type is optional. Detail: {exc}",
        ) from exc

    if not records:
        raise HTTPException(400, "No usage rows found in the CSV.")

    if org_id not in _usage_store:
        _usage_store[org_id] = []
    _usage_store[org_id].extend(records)

    providers = sorted({r.provider for r in records})
    regions = sorted({f"{r.provider}/{r.region}" for r in records})
    total_energy = sum(r.energy_kwh for r in records)

    return UsageIngestionResponse(
        records_ingested=len(records),
        total_energy_kwh=round(total_energy, 4),
        providers_covered=providers,
        regions_covered=regions,
    )


@router.post("/calculate", response_model=CalculationResponse)
async def calculate_emissions(req: CalculateRequest) -> CalculationResponse:
    """Calculate emissions from ingested usage data for an organization."""
    records = _usage_store.get(req.org_id, [])
    if not records:
        raise HTTPException(404, f"No usage data found for org {req.org_id}. Ingest usage first.")

    calculator = EmissionsCalculator(
        carbon_source=get_carbon_source(),
        grid_mapper=get_grid_mapper(),
    )
    calculations = await calculator.calculate(records, method=req.method)

    if req.org_id not in _calculation_store:
        _calculation_store[req.org_id] = []
    _calculation_store[req.org_id].extend(calculations)

    scope2 = sum(c.emissions_kgco2e for c in calculations if c.scope.value == "scope_2")
    scope3 = sum(c.emissions_kgco2e for c in calculations if c.scope.value == "scope_3_cat1")
    sources = sorted({c.emission_factor_source for c in calculations})

    return CalculationResponse(
        calculations_count=len(calculations),
        total_emissions_kgco2e=round(scope2 + scope3, 4),
        scope2_kgco2e=round(scope2, 4),
        scope3_kgco2e=round(scope3, 4),
        data_sources_used=sources,
    )


@router.post("/reports/generate", response_model=ComplianceReport)
async def generate_report(req: GenerateReportRequest) -> ComplianceReport:
    """Generate a CSRD-aligned compliance report from calculated emissions."""
    calculations = _calculation_store.get(req.org_id, [])
    if not calculations:
        raise HTTPException(
            404,
            f"No emissions calculations for org {req.org_id}. Run /calculate first.",
        )

    # Filter by period if specified
    filtered = calculations
    if req.period_start:
        filtered = [c for c in filtered if c.period_start >= req.period_start]
    if req.period_end:
        filtered = [c for c in filtered if c.period_end <= req.period_end]

    if not filtered:
        raise HTTPException(404, "No calculations match the specified period.")

    engine = ReportingEngine()
    report = engine.generate_report(
        org_id=req.org_id,
        org_name=req.org_name,
        calculations=filtered,
        report_name=req.report_name,
    )

    if req.org_id not in _report_store:
        _report_store[req.org_id] = []
    _report_store[req.org_id].append(report)

    return report


@router.get("/reports", response_model=list[ComplianceReportSummary])
async def list_reports(org_id: str = Query(...)) -> list[ComplianceReportSummary]:
    """List all compliance reports for an organization."""
    reports = _report_store.get(org_id, [])
    engine = ReportingEngine()
    return [engine.summarize(r) for r in reports]


@router.get("/reports/{report_id}", response_model=ComplianceReport)
async def get_report(report_id: str, org_id: str = Query(...)) -> ComplianceReport:
    """Get a specific compliance report by ID."""
    reports = _report_store.get(org_id, [])
    for r in reports:
        if r.id == report_id:
            return r
    raise HTTPException(404, f"Report {report_id} not found")


@router.get("/reports/{report_id}/export")
async def export_report(
    report_id: str,
    org_id: str = Query(...),
    format: str = Query("json", pattern="^(json|csv)$"),
):
    """Export a compliance report as JSON or CSV."""
    from fastapi.responses import Response

    reports = _report_store.get(org_id, [])
    report = None
    for r in reports:
        if r.id == report_id:
            report = r
            break
    if not report:
        raise HTTPException(404, f"Report {report_id} not found")

    if format == "csv":
        lines = [
            "metric,value",
            f"report_name,{report.report_name}",
            f"period_start,{report.period_start.isoformat()}",
            f"period_end,{report.period_end.isoformat()}",
            f"generated_at,{report.generated_at.isoformat()}",
            f"methodology,{report.methodology}",
            f"reporting_standard,{report.reporting_standard}",
            "",
            "scope,method,kgCO2e",
            f"Scope 2,Location-based,{report.scope2_location_kgco2e}",
            f"Scope 2,Market-based,{report.scope2_market_kgco2e}",
            f"Scope 3 Cat 1,Location-based,{report.scope3_cat1_kgco2e}",
            f"Total,,{report.total_kgco2e}",
            "",
            "metric,value",
            f"total_energy_kwh,{report.total_energy_kwh}",
            f"avg_renewable_percentage,{report.avg_renewable_percentage}",
            f"carbon_saved_kgco2e,{report.carbon_saved_kgco2e}",
            f"carbon_saved_percentage,{report.carbon_saved_percentage}",
            f"total_cloud_regions,{report.total_cloud_regions_used}",
            f"total_providers,{report.total_providers_used}",
            f"calculation_count,{report.calculation_count}",
            "",
            "provider,kgCO2e",
        ]
        for prov, val in report.scope2_location_by_provider.items():
            lines.append(f"{prov},{val}")
        lines.append("")
        lines.append("region,kgCO2e")
        for reg, val in report.scope2_location_by_region.items():
            lines.append(f"{reg},{val}")

        csv_content = "\n".join(lines)
        return Response(
            content=csv_content,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={report_id}.csv"},
        )

    # JSON export
    return Response(
        content=report.model_dump_json(indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={report_id}.json"},
    )


@router.get("/usage", response_model=list[CloudUsageRecord])
async def list_usage(
    org_id: str = Query(...),
    provider: str | None = Query(None),
) -> list[CloudUsageRecord]:
    """List ingested usage records for an organization."""
    records = _usage_store.get(org_id, [])
    if provider:
        records = [r for r in records if r.provider == provider]
    return records


@router.get("/calculations", response_model=list[EmissionsCalculation])
async def list_calculations(
    org_id: str = Query(...),
    scope: str | None = Query(None),
) -> list[EmissionsCalculation]:
    """List emissions calculations for an organization."""
    calcs = _calculation_store.get(org_id, [])
    if scope:
        calcs = [c for c in calcs if c.scope.value == scope]
    return calcs
