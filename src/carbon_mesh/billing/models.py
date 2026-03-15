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


# Tier definitions — Green ZK Broker pricing
TIERS: dict[str, PlanInfo] = {
    "free": PlanInfo(
        tier="free",
        name="Free",
        daily_limit=100,
        price_cents=0,
        features=[
            "100 API requests/day",
            "Simulated proof routing",
            "Mock prover networks",
            "Live carbon intensity data",
            "Community support",
        ],
    ),
    "pro": PlanInfo(
        tier="pro",
        name="Pro",
        daily_limit=50_000,
        price_cents=9900,  # $99/mo + 5% of bounties
        features=[
            "50,000 API requests/day",
            "Live prover network connections",
            "All 11 carbon data sources",
            "Automated job dispatch",
            "Carbon policy engine",
            "Earnings dashboard + CSV export",
            "5% broker fee on bounties",
            "Email support",
        ],
    ),
    "enterprise": PlanInfo(
        tier="enterprise",
        name="Enterprise",
        daily_limit=1_000_000,
        price_cents=0,  # Custom — negotiated broker fee
        features=[
            "Unlimited API requests",
            "Custom prover network integrations",
            "Private GPU fleet management",
            "Behind-the-meter facility routing",
            "Custom carbon policy + SLAs",
            "Multi-org tenant isolation",
            "Negotiated broker fee",
            "White-label API",
            "Dedicated support + SLA",
        ],
    ),
}
