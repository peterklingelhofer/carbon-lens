"""Tests for the carbon-aware HTTP shedder middleware."""

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
