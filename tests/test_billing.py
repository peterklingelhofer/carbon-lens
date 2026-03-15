"""Tests for billing models and API endpoints."""

from fastapi.testclient import TestClient

from carbon_mesh.billing.models import TIERS, BillingStatus, PlanInfo


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestTiers:
    def test_tiers_has_expected_keys(self):
        assert "free" in TIERS
        assert "pro" in TIERS
        assert "enterprise" in TIERS

    def test_tiers_values_are_plan_info(self):
        for plan in TIERS.values():
            assert isinstance(plan, PlanInfo)

    def test_free_tier_defaults(self):
        free = TIERS["free"]
        assert free.tier == "free"
        assert free.name == "Free"
        assert free.daily_limit == 100
        assert free.price_cents == 0
        assert isinstance(free.features, list)
        assert len(free.features) > 0

    def test_pro_tier_pricing(self):
        pro = TIERS["pro"]
        assert pro.tier == "pro"
        assert pro.price_cents == 9900
        assert pro.daily_limit == 50_000

    def test_enterprise_tier(self):
        ent = TIERS["enterprise"]
        assert ent.tier == "enterprise"
        assert ent.daily_limit == 1_000_000


class TestPlanInfo:
    def test_plan_info_fields(self):
        plan = PlanInfo(
            tier="test",
            name="Test Plan",
            daily_limit=50,
            price_cents=100,
            features=["feature_a"],
        )
        assert plan.tier == "test"
        assert plan.name == "Test Plan"
        assert plan.daily_limit == 50
        assert plan.price_cents == 100
        assert plan.features == ["feature_a"]

    def test_plan_info_serialization(self):
        plan = TIERS["free"]
        data = plan.model_dump()
        assert set(data.keys()) == {"tier", "name", "daily_limit", "price_cents", "features"}


class TestBillingStatus:
    def test_billing_status_construction(self):
        plan = TIERS["free"]
        status = BillingStatus(
            api_key_id=None,
            tier="free",
            plan=plan,
            today_usage=5,
            daily_limit=100,
            remaining=95,
        )
        assert status.api_key_id is None
        assert status.tier == "free"
        assert status.plan == plan
        assert status.today_usage == 5
        assert status.remaining == 95

    def test_billing_status_with_api_key(self):
        plan = TIERS["pro"]
        status = BillingStatus(
            api_key_id="key-123",
            tier="pro",
            plan=plan,
            today_usage=500,
            daily_limit=10_000,
            remaining=9_500,
        )
        assert status.api_key_id == "key-123"
        assert status.tier == "pro"


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------


class TestBillingEndpoints:
    def test_list_plans(self, client: TestClient):
        resp = client.get("/api/v1/billing/plans")
        assert resp.status_code == 200
        plans = resp.json()
        assert isinstance(plans, list)
        assert len(plans) == 3

        tiers_returned = {p["tier"] for p in plans}
        assert tiers_returned == {"free", "pro", "enterprise"}

        for plan in plans:
            assert "tier" in plan
            assert "name" in plan
            assert "daily_limit" in plan
            assert "price_cents" in plan
            assert "features" in plan
            assert isinstance(plan["features"], list)

    def test_billing_status_no_auth(self, client: TestClient):
        resp = client.get("/api/v1/billing/status")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tier"] == "free"
        assert data["api_key_id"] is None
        assert data["daily_limit"] == 100
        assert data["remaining"] == 100
        assert data["today_usage"] == 0
        assert "plan" in data
        assert data["plan"]["tier"] == "free"
