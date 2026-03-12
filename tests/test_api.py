from fastapi.testclient import TestClient


def test_health(client: TestClient):
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "carbon_source" in data


def test_route_endpoint(client: TestClient):
    resp = client.post(
        "/api/v1/route",
        json={
            "constraints": {
                "providers": ["aws", "gcp"],
                "carbon_weight": 1.0,
                "cost_weight": 0.0,
            }
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "recommended" in data
    assert data["recommended"]["renewable_percentage"] >= 90


def test_route_with_residency(client: TestClient):
    resp = client.post(
        "/api/v1/route",
        json={
            "constraints": {
                "providers": ["aws"],
                "data_residency": ["EU"],
            }
        },
    )
    assert resp.status_code == 200
    rec = resp.json()["recommended"]
    assert rec["region"].startswith("eu-")


def test_list_regions(client: TestClient):
    resp = client.get("/api/v1/regions")
    assert resp.status_code == 200
    regions = resp.json()
    assert len(regions) > 30


def test_list_regions_by_provider(client: TestClient):
    resp = client.get("/api/v1/regions?provider=gcp")
    assert resp.status_code == 200
    regions = resp.json()
    assert all(r["provider"] == "gcp" for r in regions)


def test_get_carbon_intensity(client: TestClient):
    resp = client.get("/api/v1/carbon/aws/us-west-2")
    assert resp.status_code == 200
    data = resp.json()
    assert data["grid_zone"] == "US-NW-BPAT"
    assert data["renewable_percentage"] == 90


def test_get_carbon_unknown_region(client: TestClient):
    resp = client.get("/api/v1/carbon/aws/nonexistent")
    assert resp.status_code == 404


def test_accounting_savings(client: TestClient):
    # Make a route request first to generate accounting data
    client.post(
        "/api/v1/route",
        json={"constraints": {"providers": ["aws"]}},
    )
    resp = client.get("/api/v1/accounting/savings")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_requests"] >= 1
    assert data["total_carbon_saved_gco2_kwh"] >= 0


def test_readiness_probe(client: TestClient):
    resp = client.get("/ready")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ready"


def test_security_headers(client: TestClient):
    resp = client.get("/health")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    assert "X-Request-ID" in resp.headers


def test_billing_plans(client: TestClient):
    resp = client.get("/api/v1/billing/plans")
    assert resp.status_code == 200
    plans = resp.json()
    assert len(plans) == 3
    names = {p["name"] for p in plans}
    assert names == {"Free", "Pro", "Enterprise"}
    free_plan = next(p for p in plans if p["name"] == "Free")
    assert free_plan["daily_limit"] == 100


def test_billing_status_unauthenticated(client: TestClient):
    resp = client.get("/api/v1/billing/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["tier"] == "free"


def test_provider_status(client: TestClient):
    resp = client.get("/health/providers")
    assert resp.status_code == 200
    data = resp.json()
    assert "configured" in data
    assert "missing" in data
    assert data["total_available"] == 10
    assert data["total_configured"] >= 6  # At least the no-key providers


def test_provider_status_counts(client: TestClient):
    resp = client.get("/health/providers")
    data = resp.json()
    # No-key providers always configured
    configured_names = list(data["configured"].keys())
    assert any("UK" in n for n in configured_names)
    assert any("AEMO" in n for n in configured_names)
    assert any("Open-Meteo" in n for n in configured_names)
