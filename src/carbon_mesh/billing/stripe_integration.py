"""Stripe billing integration — checkout sessions, webhooks, plan management.

Works without a Stripe key (endpoints return 503). Once CARBON_MESH_STRIPE_SECRET_KEY
is set, all billing flows activate automatically.
"""

import logging

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from carbon_mesh.config import settings
from carbon_mesh.db.models import Organization

logger = logging.getLogger(__name__)

# Lazy-import stripe so the app works without the package installed
_stripe = None


def _get_stripe():
    global _stripe
    if _stripe is None:
        import stripe

        stripe.api_key = settings.stripe_secret_key
        _stripe = stripe
    return _stripe


def stripe_enabled() -> bool:
    return bool(settings.stripe_secret_key)


async def create_checkout_session(
    session: AsyncSession,
    org: Organization,
    price_id: str,
    success_url: str,
    cancel_url: str,
) -> str:
    """Create a Stripe Checkout Session and return the URL."""
    stripe = _get_stripe()

    # Ensure org has a Stripe customer
    if not org.stripe_customer_id:
        customer = stripe.Customer.create(
            name=org.name,
            metadata={"org_id": org.id, "org_slug": org.slug},
        )
        await session.execute(
            update(Organization)
            .where(Organization.id == org.id)
            .values(stripe_customer_id=customer.id)
        )
        await session.commit()
        customer_id = customer.id
    else:
        customer_id = org.stripe_customer_id

    checkout = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"org_id": org.id},
    )
    return checkout.url


async def handle_webhook_event(
    session: AsyncSession,
    payload: bytes,
    sig_header: str,
) -> str:
    """Process a Stripe webhook event. Returns the event type handled."""
    stripe = _get_stripe()
    event = stripe.Webhook.construct_event(
        payload, sig_header, settings.stripe_webhook_secret
    )

    if event.type == "checkout.session.completed":
        await _handle_checkout_completed(session, event.data.object)
    elif event.type == "customer.subscription.updated":
        await _handle_subscription_updated(session, event.data.object)
    elif event.type == "customer.subscription.deleted":
        await _handle_subscription_deleted(session, event.data.object)
    else:
        logger.debug("Unhandled Stripe event: %s", event.type)

    return event.type


async def _handle_checkout_completed(session: AsyncSession, checkout) -> None:
    """Upgrade org tier after successful checkout."""
    org_id = checkout.metadata.get("org_id")
    if not org_id:
        logger.warning("Checkout completed without org_id metadata")
        return

    subscription_id = checkout.subscription

    # Determine tier from the price
    tier = _price_to_tier(checkout)

    await session.execute(
        update(Organization)
        .where(Organization.id == org_id)
        .values(
            tier=tier,
            stripe_subscription_id=subscription_id,
        )
    )
    await session.commit()
    logger.info("Org %s upgraded to %s (sub: %s)", org_id, tier, subscription_id)


async def _handle_subscription_updated(session: AsyncSession, subscription) -> None:
    """Handle plan changes (upgrades/downgrades)."""
    customer_id = subscription.customer
    stmt = select(Organization).where(Organization.stripe_customer_id == customer_id)
    result = await session.execute(stmt)
    org = result.scalar_one_or_none()
    if not org:
        logger.warning("Subscription update for unknown customer: %s", customer_id)
        return

    price_id = subscription["items"]["data"][0]["price"]["id"]
    tier = "enterprise" if price_id == settings.stripe_price_id_enterprise else "pro"

    await session.execute(
        update(Organization)
        .where(Organization.id == org.id)
        .values(tier=tier, stripe_subscription_id=subscription.id)
    )
    await session.commit()
    logger.info("Org %s plan updated to %s", org.id, tier)


async def _handle_subscription_deleted(session: AsyncSession, subscription) -> None:
    """Downgrade to free when subscription is cancelled."""
    customer_id = subscription.customer
    await session.execute(
        update(Organization)
        .where(Organization.stripe_customer_id == customer_id)
        .values(tier="free", stripe_subscription_id=None)
    )
    await session.commit()
    logger.info("Subscription cancelled for customer %s — downgraded to free", customer_id)


def _price_to_tier(checkout) -> str:
    """Map a Stripe checkout to a tier name."""
    # Try to read the price from line items
    try:
        price_id = checkout.line_items.data[0].price.id
    except (AttributeError, IndexError):
        price_id = ""

    if price_id == settings.stripe_price_id_enterprise:
        return "enterprise"
    return "pro"
