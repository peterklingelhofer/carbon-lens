"""Carbon-aware Prefect integration.

Gate a flexible step in a Prefect flow on the grid: ``wait_for_clean_window`` blocks
until the region is a good time to run (or the deadline passes), then your downstream
tasks proceed. Use it as a plain call in any flow, or as a native Prefect task so it
shows up in the flow run.

    from prefect import flow
    from carbon_mesh.integrations.prefect import wait_for_clean_window

    @flow
    def nightly():
        wait_for_clean_window("aws/us-east-1", max_intensity=150, max_wait_hours=6)
        train_model()

Prefect is an optional dependency (``pip install prefect``); only the task wrapper
needs it. Reuses ``carbon_mesh.sdk`` so the decision matches every other surface.
"""

from __future__ import annotations

from typing import Any

from carbon_mesh.sdk import DEFAULT_API_URL, CarbonClient

try:
    from prefect import task as _prefect_task

    _HAS_PREFECT = True
except ImportError:  # pragma: no cover - exercised only without Prefect installed
    _prefect_task = None
    _HAS_PREFECT = False


def wait_for_clean_window(
    region: str,
    api_url: str = DEFAULT_API_URL,
    max_wait_hours: float = 24.0,
    max_intensity: float | None = None,
    poll_seconds: float = 600.0,
    report: bool = False,
) -> dict:
    """Block until ``region`` is a good time to run; returns the SDK wait result.

    With ``report=True``, the shifted run's predicted impact is posted to the org
    ledger (best-effort) so Prefect flows feed org-statement like ``carbonlens run``."""
    return CarbonClient(api_url).wait_for_clean_window(
        region, max_wait_hours, max_intensity, poll_seconds, report=report
    )


def clean_window_task(**task_kwargs: Any):
    """``wait_for_clean_window`` wrapped as a Prefect ``@task`` (needs Prefect)."""
    if not _HAS_PREFECT:
        raise ImportError("The Prefect integration needs Prefect installed (pip install prefect).")
    task_kwargs.setdefault("name", "wait_for_clean_grid")
    return _prefect_task(**task_kwargs)(wait_for_clean_window)
