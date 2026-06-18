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

from carbon_mesh.sdk import DEFAULT_API_URL, CarbonClient, is_good_time


def defer_seconds(
    signal: dict, max_intensity: float | None = None, max_wait_hours: float = 24.0
) -> float:
    """Seconds to delay a task: 0 if now is a good time, else the time to the soonest
    clean window (surplus first, then merely-cleaner), capped at ``max_wait_hours``."""
    if is_good_time(signal, max_intensity):
        return 0.0
    hours = (
        signal.get("surplus_window_in_hours")
        or signal.get("cleaner_window_in_hours")
        or max_wait_hours
    )
    return min(float(hours), max_wait_hours) * 3600


def apply_when_clean(
    task: Any,
    region: str,
    args: tuple = (),
    kwargs: dict | None = None,
    *,
    api_url: str = DEFAULT_API_URL,
    max_wait_hours: float = 24.0,
    max_intensity: float | None = None,
) -> Any:
    """Dispatch a Celery ``task`` now if the grid is clean, else schedule it (via
    ``countdown``) for the soonest clean window. Returns the ``AsyncResult``."""
    signal = CarbonClient(api_url).signal(region)
    countdown = defer_seconds(signal, max_intensity, max_wait_hours)
    if countdown <= 0:
        return task.apply_async(args=args, kwargs=kwargs)
    return task.apply_async(args=args, kwargs=kwargs, countdown=countdown)
