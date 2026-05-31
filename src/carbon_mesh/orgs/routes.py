"""Organization management + Stripe billing endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from carbon_mesh.auth.dependencies import require_admin
from carbon_mesh.billing.stripe_integration import (
    create_checkout_session,
    handle_webhook_event,
    stripe_enabled,
)
from carbon_mesh.config import settings
from carbon_mesh.db.engine import get_session
from carbon_mesh.orgs.service import create_org, get_org, get_org_by_slug, list_orgs

org_router = APIRouter(prefix="/orgs", tags=["Organizations"])


# --- Pydantic models ---


class CreateOrgRequest(BaseModel):
    name: str


class OrgResponse(BaseModel):
    id: str
    name: str
    slug: str
    tier: str
    stripe_customer_id: str | None = None
    stripe_subscription_id: str | None = None


class CheckoutRequest(BaseModel):
    plan: str  # "pro" or "enterprise"
    success_url: str = "http://localhost:5173/settings?checkout=success"
    cancel_url: str = "http://localhost:5173/plans?checkout=cancelled"


class CheckoutResponse(BaseModel):
    checkout_url: str


# --- Org CRUD (admin-only) ---


@org_router.post("", response_model=OrgResponse, dependencies=[Depends(require_admin)])
async def create_organization(
    body: CreateOrgRequest,
    session: AsyncSession = Depends(get_session),
) -> OrgResponse:
    """Create a new organization."""
    org = await create_org(session, body.name)
    return OrgResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        tier=org.tier,
        stripe_customer_id=org.stripe_customer_id,
        stripe_subscription_id=org.stripe_subscription_id,
    )


@org_router.get("", response_model=list[OrgResponse], dependencies=[Depends(require_admin)])
async def list_organizations(
    session: AsyncSession = Depends(get_session),
) -> list[OrgResponse]:
    """List all organizations."""
    orgs = await list_orgs(session)
    return [
        OrgResponse(
            id=o.id,
            name=o.name,
            slug=o.slug,
            tier=o.tier,
            stripe_customer_id=o.stripe_customer_id,
            stripe_subscription_id=o.stripe_subscription_id,
        )
        for o in orgs
    ]


@org_router.get("/{slug}", response_model=OrgResponse, dependencies=[Depends(require_admin)])
async def get_organization(
    slug: str,
    session: AsyncSession = Depends(get_session),
) -> OrgResponse:
    """Get organization by slug."""
    org = await get_org_by_slug(session, slug)
    if not org:
        raise HTTPException(status_code=404, detail=f"Organization not found: {slug}")
    return OrgResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        tier=org.tier,
        stripe_customer_id=org.stripe_customer_id,
        stripe_subscription_id=org.stripe_subscription_id,
    )


# --- Stripe billing ---


@org_router.post("/{org_id}/checkout", response_model=CheckoutResponse)
async def create_billing_checkout(
    org_id: str,
    body: CheckoutRequest,
    session: AsyncSession = Depends(get_session),
) -> CheckoutResponse:
    """Create a Stripe Checkout Session to upgrade an org's plan."""
    if not stripe_enabled():
        raise HTTPException(
            status_code=503,
            detail="Stripe not configured. Set CARBON_MESH_STRIPE_SECRET_KEY to enable billing.",
        )

    org = await get_org(session, org_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    price_map = {
        "pro": settings.stripe_price_id_pro,
        "enterprise": settings.stripe_price_id_enterprise,
    }
    price_id = price_map.get(body.plan)
    if not price_id:
        raise HTTPException(
            status_code=400, detail=f"Unknown plan: {body.plan}. Use 'pro' or 'enterprise'."
        )

    url = await create_checkout_session(session, org, price_id, body.success_url, body.cancel_url)
    return CheckoutResponse(checkout_url=url)


# --- Stripe webhooks (mounted separately, no auth) ---

webhook_router = APIRouter(tags=["Stripe Webhooks"])


@webhook_router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Handle Stripe webhook events (checkout, subscription changes)."""
    if not stripe_enabled():
        raise HTTPException(status_code=503, detail="Stripe not configured")

    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")

    try:
        event_type = await handle_webhook_event(session, payload, sig)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Webhook error: {e}")

    return {"status": "ok", "event_type": event_type}
