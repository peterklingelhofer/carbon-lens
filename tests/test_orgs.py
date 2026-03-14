"""Tests for organization management and Stripe billing integration."""

import pytest

from carbon_mesh.orgs.service import _slugify
from carbon_mesh.billing.stripe_integration import stripe_enabled


class TestSlugify:
    def test_simple_name(self):
        assert _slugify("Acme Corp") == "acme-corp"

    def test_special_characters(self):
        assert _slugify("My Company! @#$") == "my-company"

    def test_unicode(self):
        assert _slugify("Über Tech") == "ber-tech"

    def test_numbers(self):
        assert _slugify("Company 123") == "company-123"

    def test_empty_string(self):
        assert _slugify("") == "org"

    def test_only_special_chars(self):
        assert _slugify("@#$%") == "org"

    def test_leading_trailing_dashes(self):
        assert _slugify("--hello--") == "hello"


class TestStripeEnabled:
    def test_stripe_disabled_by_default(self):
        assert stripe_enabled() is False


class TestOrgEndpoints:
    """Test org endpoints return appropriate responses without DB."""

    def test_stripe_checkout_returns_503_without_key(self, client):
        resp = client.post(
            "/api/v1/orgs/fake-org-id/checkout",
            json={"plan": "pro"},
        )
        assert resp.status_code == 503
        assert "Stripe not configured" in resp.json()["detail"]

    def test_stripe_webhook_returns_503_without_key(self, client):
        resp = client.post(
            "/api/v1/webhooks/stripe",
            content=b"{}",
            headers={"stripe-signature": "fake"},
        )
        assert resp.status_code == 503


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from carbon_mesh.main import app
    return TestClient(app)
