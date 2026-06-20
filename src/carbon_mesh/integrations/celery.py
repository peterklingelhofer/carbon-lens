"""Carbon-aware Celery integration.

Schedule a flexible Celery task for the next clean window instead of blocking a
worker: ``apply_when_clean`` reads the grid signal and either dispatches the task now
(good time) or schedules it with a ``countdown`` to the soonest cleaner/surplus
window, capped at ``max_wait_hours``. It uses Celery's own broker-side scheduling, so
no worker is held while waiting.

    from carbon_mesh.integrations.celery import apply_when_clean

    apply_when_clean(train_model, "aws/us-east-1", args=(dataset,), max_intensity=150)

Celery isn't imported here -- this just calls your task's ``.apply_async``, so it
works with any Celery task. Reuses ``carbon_mesh.sdk`` for the decision.
"""

from __future__ import annotations

from typing import Any

from carbon_mesh.sdk import (
    DEFAULT_API_URL,
    CarbonClient,
    impact_from_signal,
    is_good_time,
    soonest_clean_window_hours,
)


def defer_seconds(
    signal: dict, max_intensity: float | None = None, max_wait_hours: float = 24.0
) -> float:
    """Seconds to delay a task: 0 if now is a good time, else the time to the soonest
    clean window (surplus first, then merely-cleaner), capped at ``max_wait_hours``."""
    if is_good_time(signal, max_intensity):
        return 0.0
    hours = soonest_clean_window_hours(signal, max_wait_hours)
    return min(hours, max_wait_hours) * 3600


def apply_when_clean(
    task: Any,
    region: str,
    args: tuple = (),
    kwargs: dict | None = None,
    *,
    api_url: str = DEFAULT_API_URL,
    max_wait_hours: float = 24.0,
    max_intensity: float | None = None,
    report: bool = False,
) -> Any:
    """Dispatch a Celery ``task`` now if the grid is clean, else schedule it (via
    ``countdown``) for the soonest clean window. Returns the ``AsyncResult``.

    With ``report=True``, the deferral's predicted impact is posted to the org ledger
    (best-effort; a reporting failure never blocks the dispatch)."""
    client = CarbonClient(api_url)
    signal = client.signal(region)
    countdown = defer_seconds(signal, max_intensity, max_wait_hours)
    if countdown <= 0:
        return task.apply_async(args=args, kwargs=kwargs)
    if report:
        try:
            client.report_impact(impact_from_signal(region, signal, countdown / 3600))
        except Exception:
            pass
    return task.apply_async(args=args, kwargs=kwargs, countdown=countdown)
