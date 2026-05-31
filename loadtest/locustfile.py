"""Locust load tests for CarbonLens.

Run:
    pip install locust
    locust -f loadtest/locustfile.py --host http://localhost:8000

Or headless:
    locust -f loadtest/locustfile.py --host http://localhost:8000 \
        --headless -u 50 -r 10 --run-time 60s
"""

import random

from locust import HttpUser, between, task


# Regions to test with — mix of providers
REGIONS = [
    ("aws", "us-east-1"),
    ("aws", "eu-west-1"),
    ("aws", "us-west-2"),
    ("aws", "ap-southeast-1"),
    ("gcp", "us-central1"),
    ("gcp", "europe-west1"),
    ("azure", "eastus"),
    ("azure", "westeurope"),
]

PROVIDERS = ["aws", "gcp", "azure"]


class CarbonMeshUser(HttpUser):
    """Simulates a typical API consumer."""

    wait_time = between(0.5, 2)

    @task(5)
    def route_workload(self):
        """POST /api/v1/route — the primary endpoint."""
        providers = random.sample(PROVIDERS, k=random.randint(1, 3))
        self.client.post(
            "/api/v1/route",
            json={
                "constraints": {
                    "providers": providers,
                    "carbon_weight": round(random.uniform(0.5, 1.0), 2),
                    "cost_weight": round(random.uniform(0.0, 0.5), 2),
                }
            },
            name="/api/v1/route",
        )

    @task(3)
    def get_carbon_intensity(self):
        """GET /api/v1/carbon/{provider}/{region}"""
        provider, region = random.choice(REGIONS)
        self.client.get(
            f"/api/v1/carbon/{provider}/{region}",
            name="/api/v1/carbon/[provider]/[region]",
        )

    @task(2)
    def batch_carbon(self):
        """POST /api/v1/carbon/batch — multi-region lookup."""
        sample = random.sample(REGIONS, k=random.randint(2, 5))
        self.client.post(
            "/api/v1/carbon/batch",
            json=[{"provider": p, "region": r} for p, r in sample],
            name="/api/v1/carbon/batch",
        )

    @task(2)
    def list_regions(self):
        """GET /api/v1/regions — should be fast (cached + ETag)."""
        self.client.get("/api/v1/regions", name="/api/v1/regions")

    @task(1)
    def list_regions_filtered(self):
        """GET /api/v1/regions?provider=aws"""
        provider = random.choice(PROVIDERS)
        self.client.get(
            f"/api/v1/regions?provider={provider}",
            name="/api/v1/regions?provider=[p]",
        )

    @task(1)
    def health_check(self):
        """GET /health"""
        self.client.get("/health", name="/health")

    @task(1)
    def billing_plans(self):
        """GET /api/v1/billing/plans"""
        self.client.get("/api/v1/billing/plans", name="/api/v1/billing/plans")


class HeavyUser(HttpUser):
    """Simulates a high-throughput consumer (CI/CD pipeline, Terraform)."""

    wait_time = between(0.1, 0.5)
    weight = 1  # 1 heavy user per 3 normal users

    @task(10)
    def rapid_route(self):
        """Rapid-fire route requests."""
        self.client.post(
            "/api/v1/route",
            json={
                "constraints": {
                    "providers": ["aws", "gcp", "azure"],
                    "carbon_weight": 0.8,
                    "cost_weight": 0.2,
                }
            },
            name="/api/v1/route [heavy]",
        )

    @task(5)
    def batch_all_regions(self):
        """Batch fetch all popular regions at once."""
        self.client.post(
            "/api/v1/carbon/batch",
            json=[{"provider": p, "region": r} for p, r in REGIONS],
            name="/api/v1/carbon/batch [heavy]",
        )
