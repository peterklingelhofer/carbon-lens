"""Billing and usage API endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from carbon_mesh.api.deps import get_session
from carbon_mesh.auth.dependencies import require_api_key
from carbon_mesh.billing.models import TIERS, BillingStatus, PlanInfo
from carbon_mesh.billing.usage import check_usage_limit
from carbon_mesh.config import settings
from carbon_mesh.db.models import ApiKeyRecord

billing_router = APIRouter(prefix="/billing", tags=["Billing"])


@billing_router.get("/plans", response_model=list[PlanInfo])
async def list_plans() -> list[PlanInfo]:
    """List all available subscription plans."""
    return list(TIERS.values())


@billing_router.get("/status", response_model=BillingStatus)
async def billing_status(
    key: ApiKeyRecord | None = Depends(require_api_key),
    session: AsyncSession | None = Depends(get_session),
) -> BillingStatus:
    """Get billing status and usage for current API key."""
    if not settings.use_database or session is None or key is None:
        free_plan = TIERS["free"]
        return BillingStatus(
            api_key_id=None,
            tier="free",
            plan=free_plan,
            today_usage=0,
            daily_limit=free_plan.daily_limit,
            remaining=free_plan.daily_limit,
        )

    return await check_usage_limit(session, key)
