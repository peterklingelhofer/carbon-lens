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
import os
import time
from collections.abc import Callable

import httpx

DEFAULT_API_URL = "https://carbonlens-gssa.onrender.com"

# How long a fetched CDN snapshot is reused before refetching (matches the publish
# cadence). Reading signals from the snapshot avoids waking the API on every call.
_SNAPSHOT_TTL_SECONDS = 300.0


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


def soonest_clean_window_hours(signal: dict, default: float = 0.0) -> float:
    """Hours until the soonest clean window: surplus first, then merely-cleaner, else ``default``.

    Shared by the integrations and the Kubernetes controller so they agree on which
    horizon to defer toward
    """
    hours = (
        signal.get("surplus_window_in_hours") or signal.get("cleaner_window_in_hours") or default
    )
    return float(hours)


def impact_from_signal(region: str, signal: dict, deferred_hours: float) -> dict:
    """Build an org-ledger impact entry from a signal and a chosen deferral.

    The predicted per-kWh reduction is how much cleaner the window we shift into is
    versus now. Energy is unknown at scheduling time, so it's left None -- the ledger
    stores a rate; real grams need metered energy (carbonlens run --measure-energy).
    ``basis`` mirrors the signal's marginal basis (measured vs heuristic).
    """
    now_v = signal.get("intensity_gco2_kwh") or 0
    window_v = signal.get("cleaner_window_intensity_gco2_kwh")
    reduction = (now_v - window_v) if window_v is not None else 0.0
    return {
        "region": region,
        "deferred_hours": int(round(deferred_hours)),
        "reduction_gco2_kwh": round(max(reduction, 0.0), 1),
        "energy_kwh": None,
        "basis": signal.get("marginal_basis", "heuristic"),
    }


class CarbonClient:
    """Thin programmatic client for carbon-aware decisions.

    When ``snapshot_url`` is set (or ``CARBONLENS_SNAPSHOT_URL`` is in the environment),
    ``signal`` reads the precomputed per-region decision straight from the static CDN
    snapshot -- no API call, so it never has to wait for a sleeping server to wake. It
    falls back to the live API for regions/zones the snapshot doesn't cover (e.g. on-prem
    ``zone/<id>`` signals), and for everything else (waiting loops, reporting)."""

    def __init__(
        self,
        api_url: str = DEFAULT_API_URL,
        timeout: float = 20.0,
        snapshot_url: str | None = None,
    ) -> None:
        self._base = api_url.rstrip("/")
        self._timeout = timeout
        self._snapshot_url = snapshot_url or os.environ.get("CARBONLENS_SNAPSHOT_URL") or None
        self._snapshot_cache: dict | None = None
        self._snapshot_at = 0.0

    def _load_snapshot(self, _clock: Callable[[], float] = time.monotonic) -> dict | None:
        """Fetch+cache the CDN snapshot; returns the last good copy on a fetch error."""
        if not self._snapshot_url:
            return None
        now = _clock()
        if self._snapshot_cache is not None and (now - self._snapshot_at) < _SNAPSHOT_TTL_SECONDS:
            return self._snapshot_cache
        try:
            resp = httpx.get(self._snapshot_url, timeout=self._timeout)
            resp.raise_for_status()
            self._snapshot_cache = resp.json()
            self._snapshot_at = now
        except Exception:
            return self._snapshot_cache  # serve stale (or None) rather than raise
        return self._snapshot_cache

    def _snapshot_signal(self, region: str) -> dict | None:
        """The precomputed signal for ``region`` from the CDN snapshot, or None."""
        snap = self._load_snapshot()
        if not snap:
            return None
        return (snap.get("signals") or {}).get(region)

    def signal(self, region: str) -> dict:
        """Raw signal for a ``provider/region`` or ``zone/<id>`` (for on-prem grids).

        Served from the CDN snapshot when configured and present; otherwise from the API."""
        cached = self._snapshot_signal(region)
        if cached is not None:
            return cached
        provider, _, reg = region.partition("/")
        resp = httpx.get(
            f"{self._base}/api/v1/carbon/signal/{provider}/{reg}", timeout=self._timeout
        )
        resp.raise_for_status()
        return resp.json()

    def is_good_time(self, region: str, max_intensity: float | None = None) -> bool:
        """Whether now is a good time to run flexible load in ``region``."""
        return is_good_time(self.signal(region), max_intensity)

    def report_impact(self, entry: dict) -> dict:
        """POST one carbon-aware decision's impact to this API's org ledger.

        Raises on HTTP error; callers that must never fail the underlying job should
        wrap this in try/except (the integrations do).
        """
        resp = httpx.post(
            f"{self._base}/api/v1/accounting/impact", json=entry, timeout=self._timeout
        )
        resp.raise_for_status()
        return resp.json()

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
        report: bool = False,
        _sleep: Callable[[float], None] = time.sleep,
        _clock: Callable[[], float] = time.monotonic,
    ) -> dict:
        """Block until the grid is a good time to run, or the deadline passes.

        Returns ``{"reason": "clean"|"deadline", "signal": <last signal>,
        "initial_signal": <first signal>, "waited_hours": <float>}``. Polls every
        ``poll_seconds``. With ``report=True``, posts the predicted impact to the org
        ledger when the wait actually shifted the job (best-effort; never raises).
        ``_sleep``/``_clock`` are injectable for testing.
        """
        start = _clock()
        deadline = start + max_wait_hours * 3600
        initial_signal: dict | None = None
        while True:
            signal = self.signal(region)
            if initial_signal is None:
                initial_signal = signal
            now = _clock()
            reason = None
            if is_good_time(signal, max_intensity):
                reason = "clean"
            elif now >= deadline:
                reason = "deadline"
            if reason is not None:
                result = {
                    "reason": reason,
                    "signal": signal,
                    "initial_signal": initial_signal,
                    "waited_hours": (now - start) / 3600,
                }
                if report and reason == "clean" and result["waited_hours"] > 0:
                    try:
                        self.report_impact(
                            impact_from_signal(region, initial_signal, result["waited_hours"])
                        )
                    except Exception:
                        pass
                return result
            _sleep(poll_seconds)

    def run_when_clean(
        self,
        region: str,
        max_wait_hours: float = 24,
        max_intensity: float | None = None,
        poll_seconds: float = 600,
        report: bool = False,
    ) -> Callable[[Callable], Callable]:
        """Decorator: defer the wrapped function until the grid is clean, then run it."""

        def decorator(fn: Callable) -> Callable:
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                self.wait_for_clean_window(
                    region, max_wait_hours, max_intensity, poll_seconds, report=report
                )
                return fn(*args, **kwargs)

            return wrapper

        return decorator
