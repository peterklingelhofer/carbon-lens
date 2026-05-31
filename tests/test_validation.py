"""Tests for input validation, error handling, and auth."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from carbon_mesh.models.routing import JobConstraints, VALID_PROVIDERS
from carbon_mesh.auth.api_keys import generate_api_key, hash_key, key_prefix


# ---------------------------------------------------------------------------
# Model-level validation tests
# ---------------------------------------------------------------------------


class TestJobConstraintsValidation:
    def test_valid_providers(self):
        jc = JobConstraints(providers=["aws", "gcp"])
        assert set(jc.providers) == {"aws", "gcp"}

    def test_invalid_provider_rejected(self):
        with pytest.raises(ValidationError, match="Unknown providers"):
            JobConstraints(providers=["aws", "digitalocean"])

    def test_empty_providers_rejected(self):
        with pytest.raises(ValidationError):
            JobConstraints(providers=[])

    def test_zero_weights_rejected(self):
        with pytest.raises(ValidationError, match="must be > 0"):
            JobConstraints(providers=["aws"], carbon_weight=0, cost_weight=0)

    def test_weight_out_of_range(self):
        with pytest.raises(ValidationError):
            JobConstraints(providers=["aws"], carbon_weight=1.5)

    def test_valid_providers_constant(self):
        assert VALID_PROVIDERS == {"aws", "gcp", "azure"}

    def test_all_weights_carbon(self):
        jc = JobConstraints(providers=["aws"], carbon_weight=1.0, cost_weight=0.0)
        assert jc.carbon_weight == 1.0
        assert jc.cost_weight == 0.0

    def test_data_residency_optional(self):
        jc = JobConstraints(providers=["aws"])
        assert jc.data_residency is None
        jc2 = JobConstraints(providers=["aws"], data_residency=["EU", "US"])
        assert jc2.data_residency == ["EU", "US"]


# ---------------------------------------------------------------------------
# API-level validation tests
# ---------------------------------------------------------------------------


class TestAPIValidation:
    def test_invalid_provider_returns_422(self, client: TestClient):
        resp = client.post(
            "/api/v1/route",
            json={"constraints": {"providers": ["invalid_cloud"]}},
        )
        assert resp.status_code == 422

    def test_empty_providers_returns_422(self, client: TestClient):
        resp = client.post(
            "/api/v1/route",
            json={"constraints": {"providers": []}},
        )
        assert resp.status_code == 422

    def test_missing_constraints_returns_422(self, client: TestClient):
        resp = client.post("/api/v1/route", json={})
        assert resp.status_code == 422

    def test_invalid_json_returns_422(self, client: TestClient):
        resp = client.post(
            "/api/v1/route",
            content="not json",
            headers={"Content-Type": "application/json"},
        )
        assert resp.status_code == 422

    def test_weight_out_of_range_returns_422(self, client: TestClient):
        resp = client.post(
            "/api/v1/route",
            json={"constraints": {"providers": ["aws"], "carbon_weight": 2.0}},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Health check tests
# ---------------------------------------------------------------------------


class TestHealthCheck:
    def test_health_returns_version(self, client: TestClient):
        resp = client.get("/health")
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.1.0"
        assert "carbon_source" in data

    def test_health_has_request_id(self, client: TestClient):
        resp = client.get("/health")
        assert "x-request-id" in resp.headers


# ---------------------------------------------------------------------------
# Request ID middleware tests
# ---------------------------------------------------------------------------


class TestRequestID:
    def test_response_has_request_id(self, client: TestClient):
        resp = client.get("/api/v1/regions")
        assert "x-request-id" in resp.headers

    def test_request_id_passthrough(self, client: TestClient):
        custom_id = "test-req-12345"
        resp = client.get("/api/v1/regions", headers={"X-Request-ID": custom_id})
        assert resp.headers["x-request-id"] == custom_id


# ---------------------------------------------------------------------------
# API key utility tests (no DB required)
# ---------------------------------------------------------------------------


class TestAPIKeyUtils:
    def test_generate_key_format(self):
        key = generate_api_key()
        assert key.startswith("cmesh_")
        assert len(key) == 6 + 48  # prefix + 24 bytes hex

    def test_hash_is_deterministic(self):
        key = "cmesh_abc123"
        assert hash_key(key) == hash_key(key)

    def test_hash_is_hex(self):
        h = hash_key("cmesh_test")
        assert len(h) == 64
        int(h, 16)  # should not raise

    def test_key_prefix_format(self):
        key = "cmesh_abcdef1234567890"
        prefix = key_prefix(key)
        assert prefix.startswith("cmesh_")
        assert prefix.endswith("...")
        assert len(prefix) == 13  # "cmesh_" + 4 chars + "..."


# ---------------------------------------------------------------------------
# Error response format tests
# ---------------------------------------------------------------------------


class TestErrorResponses:
    def test_404_has_detail(self, client: TestClient):
        resp = client.get("/api/v1/carbon/aws/nonexistent-region-xyz")
        assert resp.status_code == 404
        data = resp.json()
        assert "detail" in data

    def test_route_no_matching_regions(self, client: TestClient):
        resp = client.post(
            "/api/v1/route",
            json={
                "constraints": {
                    "providers": ["aws"],
                    "data_residency": ["ANTARCTICA"],
                }
            },
        )
        assert resp.status_code == 400
        data = resp.json()
        assert "detail" in data
