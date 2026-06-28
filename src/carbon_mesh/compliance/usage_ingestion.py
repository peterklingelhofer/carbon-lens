"""Cloud usage ingestion — pull billing/usage data from AWS, GCP, Azure.

Each provider adapter implements the CloudUsageAdapter protocol.
We also support manual CSV upload and a mock adapter for demos.
"""

from __future__ import annotations

import csv
import io
import logging
import re
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from carbon_mesh.models.compliance import (
    NETWORK_GB_KWH,
    PROVIDER_PUE,
    STORAGE_GB_HOUR_KWH,
    VCPU_HOUR_KWH,
    CloudUsageRecord,
)

logger = logging.getLogger(__name__)

_BQ_IDENT_RE = re.compile(r"^[A-Za-z0-9_.\-]+$")


def _validate_bq_identifier(value: str, field: str) -> str:
    if not _BQ_IDENT_RE.match(value):
        raise ValueError(f"Invalid BigQuery identifier for {field}: {value!r}")
    return value


class CloudIngestionError(Exception):
    """Raised when a live cloud-billing adapter cannot fetch usage.

    Covers a missing optional SDK (install the ``cloud`` extra) and upstream
    API/credential/permission failures, so the API layer can surface a clear
    error instead of a 500.
    """


@runtime_checkable
class CloudUsageAdapter(Protocol):
    """Protocol for pulling cloud usage data from a provider."""

    provider: str

    async def fetch_usage(
        self,
        org_id: str,
        period_start: datetime,
        period_end: datetime,
        credentials: dict[str, str] | None = None,
    ) -> list[CloudUsageRecord]: ...


def estimate_energy_kwh(
    usage_quantity: float,
    usage_unit: str,
    resource_type: str,
    provider: str,
) -> float:
    """Estimate energy consumption from cloud resource usage.

    Uses Cloud Carbon Footprint methodology:
    energy_kwh = usage * coefficient * PUE
    """
    pue = PROVIDER_PUE.get(provider, PROVIDER_PUE["default"])

    if usage_unit == "vcpu_hours":
        # Try to match instance family
        family = (
            resource_type.lower().split(".")[0]
            if "." in resource_type
            else resource_type.lower().replace("-", "_")
        )
        kwh_per_unit = VCPU_HOUR_KWH.get(family, VCPU_HOUR_KWH["default"])
        return usage_quantity * kwh_per_unit * pue

    if usage_unit == "gb_hours":
        storage_type = "ssd" if "ssd" in resource_type.lower() else "default"
        kwh_per_unit = STORAGE_GB_HOUR_KWH.get(storage_type, STORAGE_GB_HOUR_KWH["default"])
        return usage_quantity * kwh_per_unit * pue

    if usage_unit == "gb_transferred":
        return usage_quantity * NETWORK_GB_KWH * pue

    if usage_unit == "requests":
        # Lambda/Cloud Functions: ~0.0000002 kWh per request (avg 200ms @ 1 vCPU)
        return usage_quantity * 0.0000002 * pue

    # Fallback: treat as raw kWh (already computed)
    if usage_unit == "kwh":
        return usage_quantity * pue

    logger.warning("Unknown usage unit %r for %s — returning 0", usage_unit, resource_type)
    return 0.0


class ManualCSVAdapter:
    """Parse cloud usage from a CSV upload.

    Expected columns: provider, region, service, resource_type,
                      usage_quantity, usage_unit, period_start, period_end
    """

    provider = "manual"

    async def fetch_usage(
        self,
        org_id: str,
        period_start: datetime,
        period_end: datetime,
        credentials: dict[str, str] | None = None,
        csv_content: str = "",
    ) -> list[CloudUsageRecord]:
        if not csv_content:
            return []

        records: list[CloudUsageRecord] = []
        reader = csv.DictReader(io.StringIO(csv_content))
        for row in reader:
            qty = float(row["usage_quantity"])
            unit = row["usage_unit"]
            rtype = row.get("resource_type", "default")
            prov = row["provider"]
            energy = estimate_energy_kwh(qty, unit, rtype, prov)

            records.append(
                CloudUsageRecord(
                    org_id=org_id,
                    provider=prov,
                    region=row["region"],
                    service=row["service"],
                    resource_type=rtype,
                    usage_quantity=qty,
                    usage_unit=unit,
                    energy_kwh=energy,
                    period_start=datetime.fromisoformat(row["period_start"]),
                    period_end=datetime.fromisoformat(row["period_end"]),
                    source="manual_csv",
                )
            )
        return records


class AWSCostExplorerAdapter:
    """Pull usage from AWS Cost Explorer / Cost and Usage Report.

    Requires: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY (or IAM role).
    Uses ce:GetCostAndUsage with UsageQuantity metric grouped by service+region.
    """

    provider = "aws"

    async def fetch_usage(
        self,
        org_id: str,
        period_start: datetime,
        period_end: datetime,
        credentials: dict[str, str] | None = None,
    ) -> list[CloudUsageRecord]:
        try:
            import boto3
        except ImportError as e:
            raise CloudIngestionError(
                "AWS ingestion requires boto3 — install the cloud extra: uv sync --extra cloud"
            ) from e

        creds = credentials or {}
        client = boto3.client(
            "ce",
            aws_access_key_id=creds.get("aws_access_key_id"),
            aws_secret_access_key=creds.get("aws_secret_access_key"),
            region_name=creds.get("region", "us-east-1"),
        )

        request = {
            "TimePeriod": {
                "Start": period_start.strftime("%Y-%m-%d"),
                "End": period_end.strftime("%Y-%m-%d"),
            },
            "Granularity": "DAILY",
            "Metrics": ["UsageQuantity"],
            "GroupBy": [
                {"Type": "DIMENSION", "Key": "SERVICE"},
                {"Type": "DIMENSION", "Key": "REGION"},
            ],
        }

        records: list[CloudUsageRecord] = []
        next_token: str | None = None
        try:
            while True:
                if next_token:
                    request["NextPageToken"] = next_token
                response = client.get_cost_and_usage(**request)

                for result in response.get("ResultsByTime", []):
                    p_start = datetime.fromisoformat(result["TimePeriod"]["Start"]).replace(
                        tzinfo=UTC
                    )
                    p_end = datetime.fromisoformat(result["TimePeriod"]["End"]).replace(tzinfo=UTC)

                    for group in result.get("Groups", []):
                        keys = group.get("Keys", [])
                        service = keys[0] if len(keys) > 0 else "unknown"
                        region = keys[1] if len(keys) > 1 else "unknown"
                        if not region or region in ("NoRegion", "global"):
                            region = "global"
                        qty = float(group["Metrics"]["UsageQuantity"]["Amount"])
                        if qty <= 0:
                            continue

                        unit = _aws_service_to_unit(service)
                        energy = estimate_energy_kwh(qty, unit, "default", "aws")

                        records.append(
                            CloudUsageRecord(
                                org_id=org_id,
                                provider="aws",
                                region=region,
                                service=_normalize_aws_service(service),
                                resource_type="default",
                                usage_quantity=qty,
                                usage_unit=unit,
                                energy_kwh=energy,
                                period_start=p_start,
                                period_end=p_end,
                                source="aws_cur",
                            )
                        )

                next_token = response.get("NextPageToken")
                if not next_token:
                    break
        except CloudIngestionError:
            raise
        except Exception as e:
            raise CloudIngestionError(f"AWS Cost Explorer request failed: {e}") from e

        return records


class GCPBillingAdapter:
    """Pull usage from GCP BigQuery Billing Export.

    Requires: GOOGLE_APPLICATION_CREDENTIALS (service account JSON).
    Queries the billing export table for usage by service+region.
    """

    provider = "gcp"

    async def fetch_usage(
        self,
        org_id: str,
        period_start: datetime,
        period_end: datetime,
        credentials: dict[str, str] | None = None,
    ) -> list[CloudUsageRecord]:
        try:
            from google.cloud import bigquery
        except ImportError as e:
            raise CloudIngestionError(
                "GCP ingestion requires google-cloud-bigquery — install the cloud extra: "
                "uv sync --extra cloud"
            ) from e

        creds = credentials or {}
        project = _validate_bq_identifier(creds.get("project_id", ""), "project_id")
        dataset = _validate_bq_identifier(
            creds.get("billing_dataset", "billing_export"), "billing_dataset"
        )
        table = _validate_bq_identifier(
            creds.get("billing_table", "gcp_billing_export_v1"), "billing_table"
        )

        # Standard GCP path: billing data is exported to a BigQuery table; we sum
        # usage per service+region+unit over the period.
        query = f"""
            SELECT
                service.description AS service,
                location.region AS region,
                SUM(usage.amount) AS usage_quantity,
                ANY_VALUE(usage.unit) AS usage_unit
            FROM `{project}.{dataset}.{table}`
            WHERE usage_start_time >= @start AND usage_end_time <= @end
            GROUP BY service, region
        """
        try:
            client = bigquery.Client(project=project)
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("start", "TIMESTAMP", period_start),
                    bigquery.ScalarQueryParameter("end", "TIMESTAMP", period_end),
                ]
            )
            results = list(client.query(query, job_config=job_config))
        except Exception as e:
            raise CloudIngestionError(f"GCP BigQuery billing query failed: {e}") from e

        records: list[CloudUsageRecord] = []
        for row in results:
            qty = float(row.usage_quantity)
            if qty <= 0:
                continue
            unit = _normalize_gcp_unit(row.usage_unit)
            energy = estimate_energy_kwh(qty, unit, "default", "gcp")
            records.append(
                CloudUsageRecord(
                    org_id=org_id,
                    provider="gcp",
                    region=row.region or "unknown",
                    service=row.service,
                    resource_type="default",
                    usage_quantity=qty,
                    usage_unit=unit,
                    energy_kwh=energy,
                    period_start=period_start,
                    period_end=period_end,
                    source="gcp_billing",
                )
            )
        return records


class AzureCostManagementAdapter:
    """Pull usage from Azure Cost Management API.

    Requires: AZURE_TENANT_ID, AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_SUBSCRIPTION_ID.
    """

    provider = "azure"

    async def fetch_usage(
        self,
        org_id: str,
        period_start: datetime,
        period_end: datetime,
        credentials: dict[str, str] | None = None,
    ) -> list[CloudUsageRecord]:
        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.costmanagement import CostManagementClient
        except ImportError as e:
            raise CloudIngestionError(
                "Azure ingestion requires azure-mgmt-costmanagement — install the cloud extra: "
                "uv sync --extra cloud"
            ) from e

        creds = credentials or {}
        subscription_id = creds.get("subscription_id", "")
        scope = f"/subscriptions/{subscription_id}"
        query = {
            "type": "Usage",
            "timeframe": "Custom",
            "timePeriod": {
                "from": period_start.isoformat(),
                "to": period_end.isoformat(),
            },
            "dataset": {
                "granularity": "Daily",
                "aggregation": {"usageQuantity": {"name": "UsageQuantity", "function": "Sum"}},
                "grouping": [
                    {"type": "Dimension", "name": "ServiceName"},
                    {"type": "Dimension", "name": "ResourceLocation"},
                ],
            },
        }
        try:
            credential = ClientSecretCredential(
                tenant_id=creds.get("tenant_id", ""),
                client_id=creds.get("client_id", ""),
                client_secret=creds.get("client_secret", ""),
            )
            client = CostManagementClient(credential)
            # Azure's SDK accepts a plain dict for `parameters` at runtime; its
            # stubs demand a typed QueryDefinition model
            result = client.query.usage(scope=scope, parameters=query)  # pyright: ignore[reportCallIssue, reportArgumentType]
        except Exception as e:
            raise CloudIngestionError(f"Azure Cost Management query failed: {e}") from e

        # Map columns by name — the row order is defined by result.columns, not fixed.
        columns = [getattr(c, "name", "") for c in (result.columns or [])]

        def _idx(*names: str) -> int | None:
            for n in names:
                if n in columns:
                    return columns.index(n)
            return None

        qty_i = _idx("UsageQuantity", "PreTaxCost", "Cost")
        svc_i = _idx("ServiceName")
        loc_i = _idx("ResourceLocation")

        records: list[CloudUsageRecord] = []
        for row in result.rows or []:
            if qty_i is None or qty_i >= len(row):
                continue
            qty = float(row[qty_i])
            if qty <= 0:
                continue
            service = str(row[svc_i]) if svc_i is not None and svc_i < len(row) else "unknown"
            region = str(row[loc_i]) if loc_i is not None and loc_i < len(row) else "unknown"
            energy = estimate_energy_kwh(qty, "vcpu_hours", "default", "azure")

            records.append(
                CloudUsageRecord(
                    org_id=org_id,
                    provider="azure",
                    region=region,
                    service=service,
                    resource_type="default",
                    usage_quantity=qty,
                    usage_unit="vcpu_hours",
                    energy_kwh=energy,
                    period_start=period_start,
                    period_end=period_end,
                    source="azure_cost",
                )
            )
        return records


class MockUsageAdapter:
    """Generate realistic demo usage data for a given period."""

    provider = "mock"

    async def fetch_usage(
        self,
        org_id: str,
        period_start: datetime,
        period_end: datetime,
        credentials: dict[str, str] | None = None,
    ) -> list[CloudUsageRecord]:
        # Realistic demo data: a mid-size SaaS company
        demo_usage = [
            ("aws", "us-east-1", "ec2", "m6i.xlarge", 7200, "vcpu_hours"),
            ("aws", "us-east-1", "s3", "standard", 500_000, "gb_hours"),
            ("aws", "eu-west-1", "ec2", "m6g.large", 3600, "vcpu_hours"),
            ("aws", "eu-west-1", "rds", "r6g.large", 1800, "vcpu_hours"),
            ("gcp", "us-central1", "compute-engine", "n2-standard-4", 4800, "vcpu_hours"),
            ("gcp", "us-central1", "cloud-functions", "default", 2_000_000, "requests"),
            ("gcp", "europe-west1", "compute-engine", "e2-standard-2", 2400, "vcpu_hours"),
            ("azure", "eastus", "virtual-machines", "Standard_D4s_v5", 3600, "vcpu_hours"),
            ("azure", "westeurope", "virtual-machines", "Standard_B2ms", 1800, "vcpu_hours"),
            ("azure", "eastus", "blob-storage", "standard", 200_000, "gb_hours"),
        ]

        records: list[CloudUsageRecord] = []
        for prov, region, service, rtype, qty, unit in demo_usage:
            energy = estimate_energy_kwh(qty, unit, rtype, prov)
            records.append(
                CloudUsageRecord(
                    org_id=org_id,
                    provider=prov,
                    region=region,
                    service=service,
                    resource_type=rtype,
                    usage_quantity=qty,
                    usage_unit=unit,
                    energy_kwh=energy,
                    period_start=period_start,
                    period_end=period_end,
                    source="mock",
                )
            )
        return records


# --- Helpers ---


def _aws_service_to_unit(service: str) -> str:
    """Heuristic: map an AWS service to a usage unit.

    Cost Explorer's SERVICE dimension returns full names (e.g. "Amazon Simple
    Storage Service"), so match on both the long names and the short codes.
    """
    s = service.lower()
    if any(
        k in s
        for k in (
            "ec2",
            "elastic compute",
            "ecs",
            "eks",
            "lambda",
            "fargate",
            "sagemaker",
            "compute",
        )
    ):
        return "vcpu_hours"
    if any(
        k in s
        for k in ("s3", "simple storage", "ebs", "elastic block", "glacier", "fsx", "storage")
    ):
        return "gb_hours"
    if any(k in s for k in ("cloudfront", "data transfer", "vpc")):
        return "gb_transferred"
    return "vcpu_hours"  # Conservative default (covers compute-like DB services too)


def _normalize_aws_service(service: str) -> str:
    """Shorten AWS service names for display."""
    mapping = {
        "Amazon Elastic Compute Cloud": "ec2",
        "Amazon Simple Storage Service": "s3",
        "Amazon Relational Database Service": "rds",
        "AWS Lambda": "lambda",
        "Amazon CloudFront": "cloudfront",
        "Amazon ElastiCache": "elasticache",
        "Amazon DynamoDB": "dynamodb",
    }
    return mapping.get(service, service.lower().replace(" ", "-")[:30])


def _normalize_gcp_unit(unit: str) -> str:
    """Map GCP billing units to our standard units."""
    u = unit.lower()
    if "hour" in u and ("core" in u or "cpu" in u or "vcpu" in u):
        return "vcpu_hours"
    if "byte" in u and ("hour" in u or "month" in u):
        return "gb_hours"
    if "byte" in u:
        return "gb_transferred"
    if "request" in u or "invocation" in u:
        return "requests"
    return "vcpu_hours"
