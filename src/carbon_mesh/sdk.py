"""Carbon-aware decision SDK -- embed the run-now/wait decision in any Python app.

For data pipelines (Airflow, Prefect, Dagster, Celery) and scripts that run flexible
work: ask whether now is a clean time, block until a clean window, or wrap a function
so it runs only when the grid is green. Talks to a CarbonLens API over httpx (the only
dependency) and reuses the same marginal/clean-surplus intelligence as the rest of the
tool. The decision logic is a pure function so it's trivial to test.

Example
-------
    from carbon_mesh.sdk import CarbonClient

    cl = CarbonClient()  # public instance by default

    if cl.is_good_time("aws/us-east-1", max_intensity=150):
        run_batch()

    @cl.run_when_clean("aws/us-east-1", max_wait_hours=6)
    def nightly_etl():
        ...

Honest limit: ``wait_for_clean_window`` BLOCKS the calling thread. For a pipeline
worker that holds a slot (e.g. an Airflow task), prefer a short poll or your
framework's deferrable/reschedule mechanism over blocking for hours.
"""

from __future__ import annotations

import functools
import time
from collections.abc import Callable

import httpx

DEFAULT_API_URL = "https://carbonlens-gssa.onrender.com"


def is_good_time(signal: dict, max_intensity: float | None = None) -> bool:
    """Whether a signal says now is a good time to run flexible load.

    Good = ``run_now`` or clean surplus, and -- if a cap is given -- intensity at or
    under it. Mirrors the Kubernetes controller's rule so every surface agrees.
    """
    good = signal.get("advice") == "run_now" or signal.get("clean_surplus") is True
    if max_intensity is not None and (signal.get("intensity_gco2_kwh") or 0) > max_intensity:
        good = False
    return good


def choose_by_carbon(signal: dict, when_clean, when_dirty, max_intensity: float | None = None):
    """Pick one of two options by the grid: ``when_clean`` if now is good, else ``when_dirty``.

    For ALWAYS-ON work that can't defer but can do *less* when the grid is dirty --
    e.g. serve a smaller AI model, lower media bitrate, or a smaller batch size when
    dirty, and the full-quality option when clean.
    """
    return when_clean if is_good_time(signal, max_intensity) else when_dirty


def choose_by_state(signal: dict, green, yellow, red):
    """Three-way pick by the signal's traffic-light ``state`` (green/yellow/red).

    Graded degradation: full quality on green, a middle tier on yellow, the leanest
    on red. Unknown state falls back to ``red`` (the safe, lowest-carbon choice).
    """
    state = signal.get("state")
    if state == "green":
        return green
    if state == "yellow":
        return yellow
    return red


class CarbonClient:
    """Thin programmatic client for carbon-aware decisions."""

    def __init__(self, api_url: str = DEFAULT_API_URL, timeout: float = 20.0) -> None:
        self._base = api_url.rstrip("/")
        self._timeout = timeout

    def signal(self, region: str) -> dict:
        """Raw signal for a ``provider/region`` or ``zone/<id>`` (for on-prem grids)."""
        provider, _, reg = region.partition("/")
        resp = httpx.get(
            f"{self._base}/api/v1/carbon/signal/{provider}/{reg}", timeout=self._timeout
        )
        resp.raise_for_status()
        return resp.json()

    def is_good_time(self, region: str, max_intensity: float | None = None) -> bool:
        """Whether now is a good time to run flexible load in ``region``."""
        return is_good_time(self.signal(region), max_intensity)

    def choose_by_carbon(self, region, when_clean, when_dirty, max_intensity=None):
        """``when_clean`` if the grid is good in ``region`` now, else ``when_dirty``.

        e.g. ``model = cl.choose_by_carbon(region, "gpt-full", "gpt-mini")`` to serve a
        leaner AI model when the grid is dirty.
        """
        return choose_by_carbon(self.signal(region), when_clean, when_dirty, max_intensity)

    def choose_by_state(self, region, green, yellow, red):
        """Three-way pick by ``region``'s traffic-light state (graded degradation)."""
        return choose_by_state(self.signal(region), green, yellow, red)

    def wait_for_clean_window(
        self,
        region: str,
        max_wait_hours: float = 24,
        max_intensity: float | None = None,
        poll_seconds: float = 600,
        _sleep: Callable[[float], None] = time.sleep,
        _clock: Callable[[], float] = time.monotonic,
    ) -> dict:
        """Block until the grid is a good time to run, or the deadline passes.

        Returns ``{"reason": "clean"|"deadline", "signal": <last signal>}``. Polls
        every ``poll_seconds``. ``_sleep``/``_clock`` are injectable for testing.
        """
        deadline = _clock() + max_wait_hours * 3600
        while True:
            signal = self.signal(region)
            if is_good_time(signal, max_intensity):
                return {"reason": "clean", "signal": signal}
            if _clock() >= deadline:
                return {"reason": "deadline", "signal": signal}
            _sleep(poll_seconds)

    def run_when_clean(
        self,
        region: str,
        max_wait_hours: float = 24,
        max_intensity: float | None = None,
        poll_seconds: float = 600,
    ) -> Callable[[Callable], Callable]:
        """Decorator: defer the wrapped function until the grid is clean, then run it."""

        def decorator(fn: Callable) -> Callable:
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                self.wait_for_clean_window(region, max_wait_hours, max_intensity, poll_seconds)
                return fn(*args, **kwargs)

            return wrapper

        return decorator
