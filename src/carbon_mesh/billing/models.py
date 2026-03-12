"""Billing and usage tracking Pydantic models."""

from datetime import date

from pydantic import BaseModel


class UsageSummary(BaseModel):
    api_key_id: str
    date: date
    request_count: int
    tier: str
    limit: int
    remaining: int


class PlanInfo(BaseModel):
    tier: str
    name: str
    daily_limit: int
    price_cents: int
    features: list[str]


class BillingStatus(BaseModel):
    api_key_id: str | None
    tier: str
    plan: PlanInfo
    today_usage: int
    daily_limit: int
    remaining: int


# Tier definitions
TIERS: dict[str, PlanInfo] = {
    "free": PlanInfo(
        tier="free",
        name="Free",
        daily_limit=100,
        price_cents=0,
        features=["100 route requests/day", "Mock data only", "Community support"],
    ),
    "pro": PlanInfo(
        tier="pro",
        name="Pro",
        daily_limit=10_000,
        price_cents=2900,
        features=[
            "10,000 route requests/day",
            "Live grid data (EIA, ENTSO-E, AEMO, etc.)",
            "Carbon accounting dashboard",
            "Email support",
        ],
    ),
    "enterprise": PlanInfo(
        tier="enterprise",
        name="Enterprise",
        daily_limit=1_000_000,
        price_cents=0,  # Custom pricing
        features=[
            "Unlimited route requests",
            "Live grid data from all providers",
            "Carbon SLA guarantee",
            "Scope 3 emissions reports",
            "Dedicated support + SLA",
            "Custom integrations",
        ],
    ),
}
