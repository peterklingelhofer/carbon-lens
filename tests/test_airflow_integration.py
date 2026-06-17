"""Tests for the carbon-aware Airflow integration that run WITHOUT Airflow installed.

The decision logic is the SDK's (already tested); here we cover the framework glue
that's exercisable without the optional dependency.
"""

import pytest

from carbon_mesh.integrations.airflow import (
    CarbonAwareSensor,
    CarbonCleanTrigger,
    _HAS_AIRFLOW,
    _signal_url,
)


def test_signal_url_for_region_and_zone():
    assert (
        _signal_url("https://x", "aws/us-east-1") == "https://x/api/v1/carbon/signal/aws/us-east-1"
    )
    assert _signal_url("https://x/", "zone/FR") == "https://x/api/v1/carbon/signal/zone/FR"


def test_trigger_serialize_roundtrips_kwargs():
    trigger = CarbonCleanTrigger(
        region="aws/us-east-1", max_wait_hours=6, max_intensity=150, poll_seconds=30
    )
    path, kwargs = trigger.serialize()
    assert path.endswith("CarbonCleanTrigger")
    assert kwargs["region"] == "aws/us-east-1"
    assert kwargs["max_wait_hours"] == 6
    assert kwargs["max_intensity"] == 150


@pytest.mark.skipif(_HAS_AIRFLOW, reason="Airflow is installed; the guard isn't exercised")
def test_sensor_requires_airflow():
    with pytest.raises(ImportError, match="apache-airflow"):
        CarbonAwareSensor(region="aws/us-east-1")
