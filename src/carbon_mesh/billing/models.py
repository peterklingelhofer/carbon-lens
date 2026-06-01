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
        features=[
            "100 API requests/day",
            "Live carbon intensity data",
            "6 no-key grid data sources",
            "Carbon-aware region routing",
            "Community support",
        ],
    ),
    "pro": PlanInfo(
        tier="pro",
        name="Pro",
        daily_limit=50_000,
        price_cents=9900,  # $99/mo
        features=[
            "50,000 API requests/day",
            "All 11 carbon data sources",
            "GHG-Protocol compliance reports (Scope 2 + 3)",
            "Green SLA monitoring",
            "Carbon-aware scheduling",
            "CSV / JSON export",
            "Email support",
        ],
    ),
    "enterprise": PlanInfo(
        tier="enterprise",
        name="Enterprise",
        daily_limit=1_000_000,
        price_cents=0,  # Custom — contact sales
        features=[
            "Unlimited API requests",
            "Custom data source integrations",
            "Custom carbon SLAs + attestation",
            "Multi-org tenant isolation",
            "White-label API",
            "Dedicated support + SLA",
        ],
    ),
}
