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


# Tier definitions — compliance SaaS pricing
TIERS: dict[str, PlanInfo] = {
    "free": PlanInfo(
        tier="free",
        name="Free",
        daily_limit=100,
        price_cents=0,
        features=[
            "100 API requests/day",
            "Mock carbon data",
            "Basic compliance report (demo)",
            "Community support",
        ],
    ),
    "pro": PlanInfo(
        tier="pro",
        name="Pro",
        daily_limit=50_000,
        price_cents=49900,  # $499/mo
        features=[
            "50,000 API requests/day",
            "11 live government data sources",
            "CSRD / ESRS E1 compliance reports",
            "Scope 2 + Scope 3 Cat 1 calculations",
            "AWS, GCP, Azure usage ingestion",
            "CSV/JSON report export",
            "Email support",
        ],
    ),
    "enterprise": PlanInfo(
        tier="enterprise",
        name="Enterprise",
        daily_limit=1_000_000,
        price_cents=0,  # Custom pricing — $2K-$10K/mo
        features=[
            "Unlimited API requests",
            "All government data sources",
            "Full CSRD + EU Taxonomy reporting",
            "Scope 2 (location + market) + Scope 3",
            "Multi-org tenant isolation",
            "SSO / SAML integration",
            "Custom cloud provider adapters",
            "Audit trail with data provenance",
            "Dedicated support + SLA",
            "On-premise deployment option",
        ],
    ),
}
