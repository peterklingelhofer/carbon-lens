"""Tests for cloud-billing usage ingestion adapters.

The live adapters (AWS/GCP/Azure) are exercised against *mocked* SDK responses —
this proves the parsing, pagination, unit-mapping, and error handling without any
real cloud account. It does NOT verify behavior against live billing APIs.
"""

import sys
import types
from datetime import datetime, timezone

import pytest

from carbon_mesh.compliance.usage_ingestion import (
    AWSCostExplorerAdapter,
    AzureCostManagementAdapter,
    CloudIngestionError,
    GCPBillingAdapter,
    ManualCSVAdapter,
    MockUsageAdapter,
    _aws_service_to_unit,
    estimate_energy_kwh,
)

START = datetime(2026, 5, 1, tzinfo=timezone.utc)
END = datetime(2026, 5, 8, tzinfo=timezone.utc)


# --- Energy estimation + helpers ---


def test_estimate_energy_units():
    assert estimate_energy_kwh(100, "vcpu_hours", "m6i.xlarge", "aws") > 0
    assert estimate_energy_kwh(100, "gb_hours", "ssd", "aws") > 0
    assert estimate_energy_kwh(100, "gb_transferred", "default", "gcp") > 0
    assert estimate_energy_kwh(1_000_000, "requests", "default", "gcp") > 0
    # PUE multiplies a raw kwh value
    assert estimate_energy_kwh(10, "kwh", "default", "aws") >= 10
    # unknown unit -> 0
    assert estimate_energy_kwh(100, "bogus", "default", "aws") == 0.0


def test_aws_service_to_unit():
    assert _aws_service_to_unit("Amazon Elastic Compute Cloud") == "vcpu_hours"
    assert _aws_service_to_unit("Amazon Simple Storage Service") == "gb_hours"
    assert _aws_service_to_unit("Amazon CloudFront") == "gb_transferred"


# --- Mock + CSV adapters ---


async def test_mock_adapter_returns_records():
    records = await MockUsageAdapter().fetch_usage("org1", START, END)
    assert len(records) > 0
    assert all(r.energy_kwh > 0 for r in records)
    assert {r.provider for r in records} == {"aws", "gcp", "azure"}


async def test_manual_csv_adapter():
    csv_content = (
        "provider,region,service,resource_type,usage_quantity,usage_unit,period_start,period_end\n"
        "aws,us-east-1,ec2,m6i.xlarge,1000,vcpu_hours,2026-05-01,2026-05-08\n"
    )
    records = await ManualCSVAdapter().fetch_usage("org1", START, END, csv_content=csv_content)
    assert len(records) == 1
    assert records[0].provider == "aws"
    assert records[0].usage_quantity == 1000
    assert records[0].energy_kwh > 0


# --- AWS adapter (mocked boto3) ---


def _fake_boto3(pages, calls):
    class _Client:
        def get_cost_and_usage(self, **kwargs):
            calls.append(kwargs)
            return pages[len(calls) - 1]

    return types.SimpleNamespace(client=lambda *a, **k: _Client())


async def test_aws_adapter_parses_and_paginates(monkeypatch):
    page1 = {
        "ResultsByTime": [
            {
                "TimePeriod": {"Start": "2026-05-01", "End": "2026-05-02"},
                "Groups": [
                    {
                        "Keys": ["Amazon Elastic Compute Cloud", "us-east-1"],
                        "Metrics": {"UsageQuantity": {"Amount": "100.0"}},
                    },
                    {
                        "Keys": ["Amazon Simple Storage Service", "NoRegion"],
                        "Metrics": {"UsageQuantity": {"Amount": "500.0"}},
                    },
                    {  # zero usage -> skipped
                        "Keys": ["AWS Lambda", "us-east-1"],
                        "Metrics": {"UsageQuantity": {"Amount": "0"}},
                    },
                ],
            }
        ],
        "NextPageToken": "page2",
    }
    page2 = {
        "ResultsByTime": [
            {
                "TimePeriod": {"Start": "2026-05-02", "End": "2026-05-03"},
                "Groups": [
                    {
                        "Keys": ["Amazon Elastic Compute Cloud", "eu-west-1"],
                        "Metrics": {"UsageQuantity": {"Amount": "42.0"}},
                    }
                ],
            }
        ]
        # no NextPageToken -> stop
    }
    calls: list = []
    monkeypatch.setitem(sys.modules, "boto3", _fake_boto3([page1, page2], calls))

    records = await AWSCostExplorerAdapter().fetch_usage(
        "org1", START, END, {"region": "us-east-1"}
    )

    # 2 pages fetched (pagination), 3 records (zero-usage row skipped)
    assert len(calls) == 2
    assert calls[1].get("NextPageToken") == "page2"
    assert len(records) == 3
    ec2 = next(r for r in records if r.region == "us-east-1")
    assert ec2.service == "ec2" and ec2.usage_unit == "vcpu_hours" and ec2.energy_kwh > 0
    s3 = next(r for r in records if r.service == "s3")
    assert s3.region == "global"  # NoRegion normalized
    assert s3.usage_unit == "gb_hours"


async def test_aws_adapter_missing_sdk_raises(monkeypatch):
    # Injecting None makes `import boto3` raise ImportError deterministically.
    monkeypatch.setitem(sys.modules, "boto3", None)
    with pytest.raises(CloudIngestionError, match="boto3"):
        await AWSCostExplorerAdapter().fetch_usage("org1", START, END, {})


async def test_aws_adapter_api_error_wrapped(monkeypatch):
    class _Boom:
        def client(self, *a, **k):
            class _C:
                def get_cost_and_usage(self, **kw):
                    raise RuntimeError("AccessDenied")

            return _C()

    monkeypatch.setitem(sys.modules, "boto3", _Boom())
    with pytest.raises(CloudIngestionError, match="AccessDenied"):
        await AWSCostExplorerAdapter().fetch_usage("org1", START, END, {})


# --- GCP adapter (mocked google.cloud.bigquery) ---


def _install_fake_bigquery(monkeypatch, rows):
    class _Client:
        def __init__(self, *a, **k):
            pass

        def query(self, *a, **k):
            return iter(rows)

    bq = types.ModuleType("google.cloud.bigquery")
    bq.Client = _Client
    bq.QueryJobConfig = lambda **k: None
    bq.ScalarQueryParameter = lambda *a, **k: None

    google = types.ModuleType("google")
    google_cloud = types.ModuleType("google.cloud")
    google_cloud.bigquery = bq
    google.cloud = google_cloud

    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.cloud", google_cloud)
    monkeypatch.setitem(sys.modules, "google.cloud.bigquery", bq)


async def test_gcp_adapter_parses_rows(monkeypatch):
    rows = [
        types.SimpleNamespace(
            service="Compute Engine",
            region="us-central1",
            usage_quantity=3600.0,
            usage_unit="hour",
        ),
        types.SimpleNamespace(
            service="Cloud Storage",
            region=None,  # -> "unknown"
            usage_quantity=2.0,
            usage_unit="byte-seconds",
        ),
        types.SimpleNamespace(
            service="X", region="us-east1", usage_quantity=0.0, usage_unit="hour"
        ),  # skipped
    ]
    _install_fake_bigquery(monkeypatch, rows)

    records = await GCPBillingAdapter().fetch_usage(
        "org1", START, END, {"project_id": "p", "billing_dataset": "d", "billing_table": "t"}
    )
    assert len(records) == 2
    assert {r.region for r in records} == {"us-central1", "unknown"}
    assert all(r.provider == "gcp" and r.source == "gcp_billing" for r in records)
    # period comes from the request (query no longer returns per-row dates)
    assert records[0].period_start == START and records[0].period_end == END


async def test_gcp_adapter_missing_sdk_raises(monkeypatch):
    monkeypatch.setitem(sys.modules, "google.cloud.bigquery", None)
    with pytest.raises(CloudIngestionError, match="bigquery"):
        await GCPBillingAdapter().fetch_usage("org1", START, END, {})


# --- Azure adapter (mocked azure SDK), column-by-name mapping ---


def _install_fake_azure(monkeypatch, columns, rows, *, boom=False):
    col_objs = [types.SimpleNamespace(name=c) for c in columns]

    class _Query:
        def usage(self, *, scope, parameters):
            if boom:
                raise RuntimeError("InvalidAuthenticationToken")
            return types.SimpleNamespace(columns=col_objs, rows=rows)

    class _CMClient:
        def __init__(self, *a, **k):
            self.query = _Query()

    identity = types.ModuleType("azure.identity")
    identity.ClientSecretCredential = lambda **k: object()
    mgmt = types.ModuleType("azure.mgmt")
    cm = types.ModuleType("azure.mgmt.costmanagement")
    cm.CostManagementClient = _CMClient
    azure = types.ModuleType("azure")
    azure.identity = identity
    azure.mgmt = mgmt
    mgmt.costmanagement = cm

    monkeypatch.setitem(sys.modules, "azure", azure)
    monkeypatch.setitem(sys.modules, "azure.identity", identity)
    monkeypatch.setitem(sys.modules, "azure.mgmt", mgmt)
    monkeypatch.setitem(sys.modules, "azure.mgmt.costmanagement", cm)


async def test_azure_adapter_maps_columns_by_name(monkeypatch):
    # Deliberately put the aggregation column NOT first, to prove name-based mapping.
    columns = ["ServiceName", "ResourceLocation", "UsageQuantity", "UsageDate", "Currency"]
    rows = [
        ["Virtual Machines", "eastus", 3600.0, "20260501", "USD"],
        ["Storage", "westeurope", 0.0, "20260501", "USD"],  # skipped
    ]
    _install_fake_azure(monkeypatch, columns, rows)

    records = await AzureCostManagementAdapter().fetch_usage(
        "org1", START, END, {"subscription_id": "sub"}
    )
    assert len(records) == 1
    assert records[0].service == "Virtual Machines"
    assert records[0].region == "eastus"
    assert records[0].usage_quantity == 3600.0
    assert records[0].energy_kwh > 0


async def test_azure_adapter_api_error_wrapped(monkeypatch):
    _install_fake_azure(monkeypatch, [], [], boom=True)
    with pytest.raises(CloudIngestionError, match="InvalidAuthenticationToken"):
        await AzureCostManagementAdapter().fetch_usage("org1", START, END, {"subscription_id": "s"})
