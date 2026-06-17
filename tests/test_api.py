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
    # carbon_weight=1.0 minimizes carbon, so the pick must be the lowest-carbon
    # region offered. (Asserting it's also high-renewable would be wrong: a clean
    # nuclear grid can be very low-carbon yet low-renewable.)
    rec = data["recommended"]
    assert all(
        rec["carbon_intensity_gco2_kwh"] <= alt["carbon_intensity_gco2_kwh"]
        for alt in data["alternatives"]
    )


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
    assert "avg_intensity_reduction_gco2_kwh" in data
    assert data["baseline"]


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


def test_request_body_too_large(client: TestClient):
    """Requests exceeding max_request_body_bytes get 413."""
    oversized = {"data": "x" * (1_048_576 + 1)}
    resp = client.post("/api/v1/route", json=oversized)
    assert resp.status_code == 413
    assert resp.json()["error"] == "request_too_large"


def test_request_body_within_limit(client: TestClient):
    """Normal-sized requests pass the size check (may fail validation, but not 413)."""
    resp = client.post(
        "/api/v1/route",
        json={"constraints": {"providers": ["aws"]}},
    )
    assert resp.status_code != 413


def test_websocket_default_regions(client: TestClient):
    """WebSocket connects and sends a carbon_update with default regions."""
    import json

    with client.websocket_connect("/ws/carbon") as ws:
        ws.send_text(json.dumps({"interval_seconds": 1}))
        data = ws.receive_json()
        assert data["type"] == "carbon_update"
        assert "timestamp" in data
        assert isinstance(data["data"], list)
        assert len(data["data"]) > 0
        entry = data["data"][0]
        assert "provider" in entry
        assert "region" in entry
        assert "carbon_intensity_gco2_kwh" in entry


def test_websocket_custom_subscription(client: TestClient):
    """WebSocket accepts custom region subscription."""
    import json

    with client.websocket_connect("/ws/carbon") as ws:
        ws.send_text(
            json.dumps(
                {
                    "regions": [{"provider": "aws", "region": "us-east-1"}],
                    "interval_seconds": 1,
                }
            )
        )
        data = ws.receive_json()
        assert data["type"] == "carbon_update"
        assert len(data["data"]) == 1
        assert data["data"][0]["provider"] == "aws"
        assert data["data"][0]["region"] == "us-east-1"


def test_carbon_forecast(client: TestClient):
    resp = client.get("/api/v1/carbon/forecast/aws/us-west-2?hours=6")
    assert resp.status_code == 200
    data = resp.json()
    assert data["grid_zone"] == "US-NW-BPAT"
    assert data["provider"] == "aws"
    assert data["method"] in ("entsoe_day_ahead", "time_of_day_model")
    # hours=6 -> the current reading plus 6 hourly projections
    assert len(data["points"]) == 7
    assert all(p["carbon_intensity_gco2_kwh"] >= 0 for p in data["points"])


def test_carbon_forecast_unknown_region(client: TestClient):
    resp = client.get("/api/v1/carbon/forecast/aws/nonexistent")
    assert resp.status_code == 404


def test_region_badge_svg(client: TestClient):
    resp = client.get("/badge/aws/us-west-2.svg")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")
    assert "<svg" in resp.text and "gCO₂/kWh" in resp.text


def test_region_embed_widget(client: TestClient):
    resp = client.get("/embed/aws/us-west-2")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/html")
    # Framing must be allowed for the widget (no X-Frame-Options DENY here).
    assert resp.headers.get("x-frame-options") != "DENY"
    assert "frame-ancestors" in resp.headers.get("content-security-policy", "")
    assert "gCO₂/kWh" in resp.text and "aws/us-west-2" in resp.text


def test_zone_embed_not_shadowed(client: TestClient):
    resp = client.get("/embed/zone/DE")
    assert resp.status_code == 200
    assert "carbon intensity" in resp.text


def test_embed_unknown_region_is_graceful(client: TestClient):
    resp = client.get("/embed/aws/nope")
    assert resp.status_code == 200
    assert "region not found" in resp.text


def test_zone_badge_not_shadowed(client: TestClient):
    # /badge/zone/DE.svg must hit the zone route, not /badge/{provider}/{region}.svg.
    resp = client.get("/badge/zone/DE.svg")
    assert resp.status_code == 200
    assert "gCO₂/kWh" in resp.text


def test_badge_unknown_region_renders_gray_not_404(client: TestClient):
    resp = client.get("/badge/aws/nope.svg")
    assert resp.status_code == 200  # a broken image in a README is worse than "unknown"
    assert "unknown region" in resp.text


def test_carbon_zones_list(client: TestClient):
    resp = client.get("/api/v1/carbon/zones")
    assert resp.status_code == 200
    zones = resp.json()
    ids = {z["grid_zone"] for z in zones}
    assert "DE" in ids and "US-NW-BPAT" in ids
    assert len(ids) == len(zones)  # one entry per distinct zone


def test_carbon_zone_lookup_not_shadowed(client: TestClient):
    # /carbon/zone/DE must hit the zone route, not /carbon/{provider}/{region}.
    resp = client.get("/api/v1/carbon/zone/DE")
    assert resp.status_code == 200
    assert resp.json()["grid_zone"] == "DE"


def test_carbon_zone_unknown_returns_404(client: TestClient):
    resp = client.get("/api/v1/carbon/zone/NOPE")
    assert resp.status_code == 404


def test_carbon_signal(client: TestClient):
    resp = client.get("/api/v1/carbon/signal/aws/us-west-2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] in ("green", "yellow", "red")
    assert body["advice"] in ("run_now", "wait_for_cleaner")
    assert body["grid_zone"] == "US-NW-BPAT"
    assert isinstance(body["intensity_gco2_kwh"], (int, float))
    if body["advice"] == "wait_for_cleaner":
        assert body["cleaner_window_in_hours"] >= 1


def test_carbon_signal_unknown_region(client: TestClient):
    assert client.get("/api/v1/carbon/signal/aws/nope").status_code == 404


def test_zone_signal(client: TestClient):
    # On-prem / colo: ask by grid zone directly, no cloud region needed.
    resp = client.get("/api/v1/carbon/signal/zone/US-NW-BPAT")
    assert resp.status_code == 200
    body = resp.json()
    assert body["grid_zone"] == "US-NW-BPAT"
    assert body["provider"] == "zone"
    assert body["advice"] in ("run_now", "wait_for_cleaner")


def test_zone_signal_unknown_zone(client: TestClient):
    assert client.get("/api/v1/carbon/signal/zone/NOPE").status_code == 404


def test_marginal_note_honesty():
    from carbon_mesh.api.routes import _marginal_note

    # Clean on average (120) but fossil on the margin (380): shifting helps more.
    note = _marginal_note(120, 380)
    assert note is not None and "margin" in note.lower()
    # Clean on the margin too: extra demand is low-carbon, so shifting helps little.
    assert "low-carbon" in _marginal_note(120, 80).lower()
    # Unremarkable / no fuel mix: no note.
    assert _marginal_note(250, 260) is None
    assert _marginal_note(250, None) is None


def test_clean_surplus_detection():
    from carbon_mesh.engine.surplus import is_clean_surplus

    # Renewables dominant, very low carbon, clean margin -> surplus.
    assert is_clean_surplus(95, 30, 20) is True
    # High renewable but unknown margin still qualifies if carbon is very low.
    assert is_clean_surplus(90, 40, None) is True
    # Fossil on the margin disqualifies even with high renewable share.
    assert is_clean_surplus(90, 40, 400) is False
    # Modest renewable share or not-low-enough carbon: not surplus.
    assert is_clean_surplus(60, 200, 50) is False
    assert is_clean_surplus(90, 150, 20) is False


def test_surplus_offsets_over_forecast():
    from types import SimpleNamespace

    from carbon_mesh.engine.surplus import surplus_offsets

    def pt(renewable, intensity, marginal=None):
        return SimpleNamespace(
            renewable_percentage=renewable,
            carbon_intensity_gco2_kwh=intensity,
            marginal_intensity_gco2_kwh=marginal,
        )

    # Dirty now, surplus at +2h and +3h (projected points carry no marginal).
    points = [pt(40, 400, 450), pt(60, 200), pt(95, 30), pt(92, 45)]
    assert surplus_offsets(points) == [2, 3]
    assert surplus_offsets([pt(50, 300), pt(55, 250)]) == []


def test_carbon_anomaly_insufficient_without_history(client: TestClient):
    # With an empty archive -> honest "insufficient_history". Override the store so
    # the test is hermetic (the real history_url has live data CI would otherwise
    # fetch, making the absent-history case impossible to assert).
    from carbon_mesh.api.deps import get_history_store
    from carbon_mesh.carbon_sources.history_store import HistoryStore
    from carbon_mesh.main import app

    app.dependency_overrides[get_history_store] = lambda: HistoryStore("", data={"series": {}})
    try:
        resp = client.get("/api/v1/carbon/anomaly/aws/us-west-2")
        assert resp.status_code == 200
        body = resp.json()
        assert body["grid_zone"] == "US-NW-BPAT"
        assert body["status"] == "insufficient_history"
    finally:
        app.dependency_overrides.pop(get_history_store, None)


def test_carbon_anomaly_with_seeded_history(client: TestClient):
    from datetime import datetime, timedelta, timezone

    from carbon_mesh.api.deps import get_history_store
    from carbon_mesh.carbon_sources.history_store import HistoryStore
    from carbon_mesh.main import app

    now = datetime.now(timezone.utc)
    # Five same-UTC-hour readings (one per prior day) -> hour-of-day baseline of 400.
    data = {
        "series": {
            "aws/us-west-2": [
                {"t": (now - timedelta(days=d)).isoformat(), "c": 400.0, "r": 30.0}
                for d in range(1, 6)
            ]
        }
    }
    app.dependency_overrides[get_history_store] = lambda: HistoryStore("", data=data)
    try:
        body = client.get("/api/v1/carbon/anomaly/aws/us-west-2").json()
        assert body["basis"] == "hour_of_day"
        assert body["baseline_gco2_kwh"] == 400.0
        assert body["sample_size"] == 5
        assert isinstance(body["delta_pct"], (int, float))
    finally:
        app.dependency_overrides.pop(get_history_store, None)


def test_carbon_history(client: TestClient):
    from datetime import datetime, timedelta, timezone

    from carbon_mesh.api.deps import get_history_store
    from carbon_mesh.carbon_sources.history_store import HistoryStore
    from carbon_mesh.main import app

    now = datetime.now(timezone.utc)
    data = {
        "series": {
            "aws/us-west-2": [
                {"t": (now - timedelta(days=30)).isoformat(), "c": 400.0, "r": 30.0},
                {"t": (now - timedelta(hours=2)).isoformat(), "c": 120.0, "r": 70.0},
            ]
        }
    }
    app.dependency_overrides[get_history_store] = lambda: HistoryStore("", data=data)
    try:
        resp = client.get("/api/v1/carbon/history/aws/us-west-2?hours=24")
        assert resp.status_code == 200
        body = resp.json()
        assert body["grid_zone"] == "US-NW-BPAT"
        # Only the 2-hours-ago point falls inside the 24h window; the 30-day-old drops.
        assert len(body["points"]) == 1
        assert body["points"][0]["carbon_intensity_gco2_kwh"] == 120.0
    finally:
        app.dependency_overrides.pop(get_history_store, None)


def test_carbon_history_unknown_region(client: TestClient):
    resp = client.get("/api/v1/carbon/history/aws/nonexistent")
    assert resp.status_code == 404


def test_rank_hours_utc():
    from carbon_mesh.engine.recurring import rank_hours_utc

    points = [
        {"t": "2026-06-10T03:00:00+00:00", "c": 50.0},
        {"t": "2026-06-11T03:00:00+00:00", "c": 70.0},  # hour 3 mean = 60
        {"t": "2026-06-10T18:00:00+00:00", "c": 400.0},  # hour 18 mean = 400
    ]
    ranked = rank_hours_utc(points)
    assert ranked[0]["hour"] == 3
    assert ranked[0]["mean_gco2_kwh"] == 60.0
    assert ranked[0]["samples"] == 2
    assert ranked[-1]["hour"] == 18


def test_best_time_from_history(client: TestClient):
    from datetime import datetime, timedelta, timezone

    from carbon_mesh.api.deps import get_history_store
    from carbon_mesh.carbon_sources.history_store import HistoryStore
    from carbon_mesh.main import app

    now = datetime.now(timezone.utc)
    # Build 7 days of two readings per day: a clean 02:00 UTC and a dirty 18:00 UTC.
    series = []
    for d in range(7):
        day = now - timedelta(days=d)
        clean = day.replace(hour=2, minute=0, second=0, microsecond=0)
        dirty = day.replace(hour=18, minute=0, second=0, microsecond=0)
        series.append({"t": clean.isoformat(), "c": 40.0, "r": 80.0})
        series.append({"t": dirty.isoformat(), "c": 450.0, "r": 10.0})

    data = {"series": {"aws/us-west-2": series}}
    app.dependency_overrides[get_history_store] = lambda: HistoryStore("", data=data)
    try:
        resp = client.get("/api/v1/carbon/best-time/aws/us-west-2?days=14&energy_kwh=10")
        assert resp.status_code == 200
        body = resp.json()
        assert body["grid_zone"] == "US-NW-BPAT"
        assert body["basis"] == "history"
        assert body["cleanest_hour_utc"] == 2
        assert body["dirtiest_hour_utc"] == 18
        assert body["suggested_cron"] == "0 2 * * *"
        # (450 - 40) / 450 = 91.1% cleaner at the best hour.
        assert body["shift_savings_pct"] == 91.1
        # (450 - 40) gCO2/kWh * 10 kWh/day * 365 / 1000 = 1496.5 kg/yr.
        assert body["annual_kg_saved"] == 1496.5
    finally:
        app.dependency_overrides.pop(get_history_store, None)


def test_best_time_unknown_region(client: TestClient):
    assert client.get("/api/v1/carbon/best-time/aws/nope").status_code == 404


def test_zone_best_time(client: TestClient):
    from datetime import datetime, timedelta, timezone

    from carbon_mesh.api.deps import get_history_store
    from carbon_mesh.carbon_sources.history_store import HistoryStore
    from carbon_mesh.main import app

    from carbon_mesh.api.deps import get_grid_mapper
    from carbon_mesh.api.routes import _zone_representative

    # History is keyed by the zone's representative region -- compute it so the test
    # doesn't depend on dict ordering.
    rep = _zone_representative(get_grid_mapper(), "US-NW-BPAT")
    assert rep is not None
    key = f"{rep.provider}/{rep.region}"

    now = datetime.now(timezone.utc)
    series = []
    for d in range(7):
        day = now - timedelta(days=d)
        series.append({"t": day.replace(hour=2).isoformat(), "c": 40.0, "r": 80.0})
        series.append({"t": day.replace(hour=18).isoformat(), "c": 450.0, "r": 10.0})

    data = {"series": {key: series}}
    app.dependency_overrides[get_history_store] = lambda: HistoryStore("", data=data)
    try:
        resp = client.get("/api/v1/carbon/best-time/zone/US-NW-BPAT?days=14")
        assert resp.status_code == 200
        body = resp.json()
        assert body["grid_zone"] == "US-NW-BPAT"
        assert body["provider"] == "zone"
        assert body["cleanest_hour_utc"] == 2
    finally:
        app.dependency_overrides.pop(get_history_store, None)


def test_zone_best_time_unknown_zone(client: TestClient):
    assert client.get("/api/v1/carbon/best-time/zone/NOPE").status_code == 404


def test_region_weather(client: TestClient, monkeypatch):
    # Stub the live Open-Meteo fetch so the test is hermetic (no network).
    async def fake_weather(lat: float, lon: float) -> tuple[float, float]:
        return 24.0, 480.0

    monkeypatch.setattr("carbon_mesh.api.routes.fetch_weather", fake_weather)
    resp = client.get("/api/v1/carbon/weather/aws/us-west-2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["grid_zone"] == "US-NW-BPAT"
    assert body["wind_speed_kmh"] == 24.0
    assert body["solar_irradiance_w_m2"] == 480.0
    assert body["source"] == "open_meteo"


def test_region_weather_unknown_region(client: TestClient):
    resp = client.get("/api/v1/carbon/weather/aws/nonexistent")
    assert resp.status_code == 404


def test_metrics_exposes_carbon_gauges(client: TestClient):
    resp = client.get("/metrics")
    assert resp.status_code == 200
    body = resp.text
    # Carbon gauges refreshed on scrape, alongside the default HTTP metrics.
    assert "carbon_intensity_gco2_kwh" in body
    assert "carbon_renewable_percentage" in body
    # Clean-surplus gauge -- ops can alert on it to trigger carbon-aware batch scaling.
    assert "carbon_clean_surplus" in body


def test_sla_crud_and_check_flow(client: TestClient):
    """Create -> get -> check -> status -> list -> delete through the repository."""
    created = client.post(
        "/api/v1/sla/create",
        json={
            "org_id": "org-flow",
            "name": "Greenest",
            "max_carbon_intensity_gco2_kwh": 300,
            "min_renewable_percentage": 40,
        },
    )
    assert created.status_code == 200
    sid = created.json()["id"]

    assert client.get(f"/api/v1/sla/{sid}").status_code == 200
    assert any(s["id"] == sid for s in client.get("/api/v1/sla/list?org_id=org-flow").json())

    check = client.post(f"/api/v1/sla/{sid}/check")
    assert check.status_code == 200
    status = client.get(f"/api/v1/sla/{sid}/status").json()
    assert status is not None and status["sla_id"] == sid
    assert len(client.get(f"/api/v1/sla/{sid}/checks").json()) >= 1

    assert client.delete(f"/api/v1/sla/{sid}").status_code == 200
    assert client.get(f"/api/v1/sla/{sid}").status_code == 404


def test_sla_run_due_checks_is_admin_gated_and_runs(client: TestClient, monkeypatch):
    from carbon_mesh.config import settings

    monkeypatch.setattr(settings, "admin_secret", "test-admin")
    sid = client.post(
        "/api/v1/sla/create",
        json={
            "org_id": "org-cron",
            "name": "Cron",
            "max_carbon_intensity_gco2_kwh": 300,
            "min_renewable_percentage": 40,
        },
    ).json()["id"]
    try:
        # No admin secret -> rejected.
        assert client.post("/api/v1/sla/monitor/run").status_code == 403
        # With the secret -> runs and checks the never-checked (due) SLA.
        resp = client.post("/api/v1/sla/monitor/run", headers={"X-API-Key": "test-admin"})
        assert resp.status_code == 200
        assert resp.json()["checks_run"] >= 1
        assert len(client.get(f"/api/v1/sla/{sid}/checks").json()) >= 1
    finally:
        client.delete(f"/api/v1/sla/{sid}")


def test_sla_monitor_status_route_not_shadowed(client: TestClient):
    """GET /sla/monitor/status must hit the monitor route, not /{sla_id}/status.

    Regression: the literal /monitor/* routes were declared after /{sla_id}/status,
    so Starlette bound sla_id="monitor" and 404'd -- which made the dashboard's
    monitor status read fail and the Start Monitor button appear to do nothing.
    """
    resp = client.get("/api/v1/sla/monitor/status")
    assert resp.status_code == 200
    body = resp.json()
    assert "running" in body
    assert "checks_completed" in body


def test_batch_returns_all_regions_sharing_a_grid_zone(client: TestClient):
    """Regions that map to the same grid zone must each appear in the batch result.

    Regression: aws/us-east-1 and aws/us-east-2 both map to US-MIDA-PJM; a
    zone-keyed dict used to drop one of them.
    """
    resp = client.post(
        "/api/v1/carbon/batch",
        json=[
            {"provider": "aws", "region": "us-east-1"},
            {"provider": "aws", "region": "us-east-2"},
        ],
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "aws/us-east-1" in data
    assert "aws/us-east-2" in data
