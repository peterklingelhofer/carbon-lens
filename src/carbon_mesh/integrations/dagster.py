"""Carbon-aware Dagster integration.

Gate a flexible asset/op on the grid: ``clean_window_op`` builds a Dagster op that
blocks until the region is a good time to run (or the deadline passes). Wire it
upstream of your flexible ops so they only run on clean power.

    from dagster import job
    from carbon_mesh.integrations.dagster import clean_window_op

    wait = clean_window_op("aws/us-east-1", max_intensity=150, max_wait_hours=6)

    @job
    def nightly():
        train_model(wait())

Dagster is an optional dependency (``pip install dagster``). Reuses
``carbon_mesh.sdk`` so the decision matches every other surface.
"""

from __future__ import annotations

from typing import Any

from carbon_mesh.integrations import _require
from carbon_mesh.sdk import DEFAULT_API_URL, CarbonClient

try:
    from dagster import op as _dagster_op

    _HAS_DAGSTER = True
except ImportError:  # pragma: no cover - exercised only without Dagster installed
    _dagster_op = None
    _HAS_DAGSTER = False


def clean_window_op(
    region: str,
    api_url: str = DEFAULT_API_URL,
    max_wait_hours: float = 24.0,
    max_intensity: float | None = None,
    poll_seconds: float = 600.0,
    report: bool = False,
    **op_kwargs: Any,
):
    """Build a Dagster op that blocks until ``region`` is a good time to run (needs Dagster).

    With ``report=True``, the shifted run's predicted impact is posted to the org
    ledger (best-effort) so Dagster jobs feed org-statement like ``carbonlens run``."""
    _require(_HAS_DAGSTER, "Dagster", "dagster")
    op_kwargs.setdefault("name", "wait_for_clean_grid")

    @_dagster_op(**op_kwargs)
    def _wait() -> dict:
        return CarbonClient(api_url).wait_for_clean_window(
            region, max_wait_hours, max_intensity, poll_seconds, report=report
        )

    return _wait
