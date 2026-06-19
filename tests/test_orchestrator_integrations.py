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


def test_celery_defer_seconds():
    from carbon_mesh.integrations.celery import defer_seconds

    # Good now -> run immediately.
    assert defer_seconds({"advice": "run_now", "clean_surplus": False}) == 0.0
    # Dirty, surplus window in 3h -> schedule 3h out.
    dirty = {"advice": "wait_for_cleaner", "clean_surplus": False, "surplus_window_in_hours": 3}
    assert defer_seconds(dirty) == 3 * 3600
    # Dirty, no surplus but a cleaner window in 5h.
    cw = {"advice": "wait_for_cleaner", "clean_surplus": False, "cleaner_window_in_hours": 5}
    assert defer_seconds(cw) == 5 * 3600
    # Window beyond the cap is clamped to max_wait_hours.
    far = {"advice": "wait_for_cleaner", "clean_surplus": False, "surplus_window_in_hours": 40}
    assert defer_seconds(far, max_wait_hours=24) == 24 * 3600


class _FakeTask:
    def __init__(self):
        self.calls = []

    def apply_async(self, args=(), kwargs=None, countdown=None):
        self.calls.append({"args": args, "kwargs": kwargs, "countdown": countdown})
        return "async-result"


def test_celery_apply_when_clean_dispatches_or_schedules(monkeypatch):
    from carbon_mesh.integrations import celery

    # Clean now -> dispatched immediately (no countdown).
    monkeypatch.setattr(
        CarbonClient, "signal", lambda self, region: {"advice": "run_now", "clean_surplus": False}
    )
    task = _FakeTask()
    celery.apply_when_clean(task, "aws/us-east-1", args=(1,))
    assert task.calls[0]["countdown"] is None

    # Dirty with a surplus window -> scheduled with a countdown.
    monkeypatch.setattr(
        CarbonClient,
        "signal",
        lambda self, region: {
            "advice": "wait_for_cleaner",
            "clean_surplus": False,
            "surplus_window_in_hours": 2,
        },
    )
    task2 = _FakeTask()
    celery.apply_when_clean(task2, "aws/us-east-1")
    assert task2.calls[0]["countdown"] == 2 * 3600


def test_celery_apply_when_clean_reports_on_defer(monkeypatch):
    from carbon_mesh.integrations import celery

    monkeypatch.setattr(
        CarbonClient,
        "signal",
        lambda self, region: {
            "advice": "wait_for_cleaner",
            "clean_surplus": False,
            "surplus_window_in_hours": 2,
            "intensity_gco2_kwh": 500,
            "cleaner_window_intensity_gco2_kwh": 300,
            "marginal_basis": "heuristic",
        },
    )
    reported: list[dict] = []
    monkeypatch.setattr(CarbonClient, "report_impact", lambda self, entry: reported.append(entry))
    task = _FakeTask()
    celery.apply_when_clean(task, "aws/us-east-1", report=True)
    assert task.calls[0]["countdown"] == 2 * 3600
    assert reported == [
        {
            "region": "aws/us-east-1",
            "deferred_hours": 2,
            "reduction_gco2_kwh": 200.0,
            "energy_kwh": None,
            "basis": "heuristic",
        }
    ]


def test_celery_apply_when_clean_does_not_report_when_clean(monkeypatch):
    from carbon_mesh.integrations import celery

    monkeypatch.setattr(
        CarbonClient, "signal", lambda self, region: {"advice": "run_now", "clean_surplus": False}
    )
    reported: list[dict] = []
    monkeypatch.setattr(CarbonClient, "report_impact", lambda self, entry: reported.append(entry))
    task = _FakeTask()
    celery.apply_when_clean(task, "aws/us-east-1", report=True)
    assert reported == []  # dispatched now, no deferral to report
