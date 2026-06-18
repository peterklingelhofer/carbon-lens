"""Tests for the Prefect and Dagster integrations (run WITHOUT those installed)."""

import pytest

from carbon_mesh.sdk import CarbonClient


def test_prefect_wait_delegates_to_sdk(monkeypatch):
    from carbon_mesh.integrations import prefect

    monkeypatch.setattr(
        CarbonClient, "signal", lambda self, region: {"advice": "run_now", "clean_surplus": False}
    )
    result = prefect.wait_for_clean_window("aws/us-east-1")
    assert result["reason"] == "clean"


@pytest.mark.skipif(
    __import__("carbon_mesh.integrations.prefect", fromlist=["_HAS_PREFECT"])._HAS_PREFECT,
    reason="Prefect is installed; the guard isn't exercised",
)
def test_prefect_task_requires_prefect():
    from carbon_mesh.integrations import prefect

    with pytest.raises(ImportError, match="prefect"):
        prefect.clean_window_task()


@pytest.mark.skipif(
    __import__("carbon_mesh.integrations.dagster", fromlist=["_HAS_DAGSTER"])._HAS_DAGSTER,
    reason="Dagster is installed; the guard isn't exercised",
)
def test_dagster_op_requires_dagster():
    from carbon_mesh.integrations import dagster

    with pytest.raises(ImportError, match="[Dd]agster"):
        dagster.clean_window_op("aws/us-east-1")
