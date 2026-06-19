"""Tests for the carbon-aware HTTP shedder middleware."""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from carbon_mesh.middleware import CarbonAwareShedder, carbon_mode


def test_carbon_mode():
    assert carbon_mode({"advice": "run_now", "clean_surplus": False}) == "full"
    assert carbon_mode({"advice": "wait_for_cleaner", "clean_surplus": False}) == "reduced"


class _FakeClient:
    def __init__(self, signal):
        self._signal = signal

    def signal(self, region):
        return self._signal


def _app(signal, **kwargs):
    app = FastAPI()
    app.add_middleware(
        CarbonAwareShedder, region="aws/us-east-1", client=_FakeClient(signal), **kwargs
    )

    @app.get("/")
    def root():
        return {"ok": True}

    return TestClient(app)


def test_tags_responses_with_mode_and_intensity():
    clean = {"advice": "run_now", "clean_surplus": False, "intensity_gco2_kwh": 90}
    resp = _app(clean).get("/")
    assert resp.status_code == 200
    assert resp.headers["X-Carbon-Mode"] == "full"
    assert resp.headers["X-Carbon-Intensity"] == "90"

    dirty = {"advice": "wait_for_cleaner", "clean_surplus": False, "intensity_gco2_kwh": 500}
    assert _app(dirty).get("/").headers["X-Carbon-Mode"] == "reduced"


def test_sheds_optional_requests_when_dirty():
    dirty = {"advice": "wait_for_cleaner", "clean_surplus": False, "intensity_gco2_kwh": 500}
    client = _app(dirty, shed_optional=True)
    # Optional request is shed with 503 + Retry-After.
    resp = client.get("/", headers={"X-Carbon-Optional": "1"})
    assert resp.status_code == 503
    assert resp.headers["Retry-After"] == "600"
    # A normal request still goes through (just degraded mode).
    assert client.get("/").status_code == 200


def test_does_not_shed_when_clean():
    clean = {"advice": "run_now", "clean_surplus": False, "intensity_gco2_kwh": 90}
    resp = _app(clean, shed_optional=True).get("/", headers={"X-Carbon-Optional": "1"})
    assert resp.status_code == 200


class _MutableClient:
    """A blocking SDK-style client whose returned signal can change between calls."""

    def __init__(self, signal):
        self._signal = signal
        self.calls = 0

    def signal(self, region):
        self.calls += 1
        return self._signal


@pytest.mark.asyncio
async def test_refresh_is_non_blocking_and_stale_while_revalidate():
    """The first request awaits the fetch; later refreshes happen in the background
    and serve the last good signal, so the synchronous client never blocks the loop."""
    t = {"now": 1000.0}
    client = _MutableClient({"advice": "run_now", "intensity_gco2_kwh": 90})
    mw = CarbonAwareShedder(
        app=None,
        region="aws/us-east-1",
        client=client,
        refresh_seconds=300.0,
        _clock=lambda: t["now"],
    )

    # First call: nothing cached, so it awaits the (threaded) fetch and returns it.
    assert (await mw._current_signal())["intensity_gco2_kwh"] == 90
    assert client.calls == 1

    # Within the window: served from cache, no new fetch.
    assert (await mw._current_signal())["intensity_gco2_kwh"] == 90
    assert client.calls == 1

    # Past the window with a new upstream value: the call returns the STALE signal
    # immediately and kicks off a background refresh (never blocking on the network).
    client._signal = {"advice": "wait_for_cleaner", "intensity_gco2_kwh": 500}
    t["now"] += 301.0
    assert (await mw._current_signal())["intensity_gco2_kwh"] == 90  # stale served now
    await mw._refresh_task  # let the background refresh land
    assert client.calls == 2

    # The refreshed value is visible on the next request.
    assert (await mw._current_signal())["intensity_gco2_kwh"] == 500
