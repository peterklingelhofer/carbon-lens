"""Organization CRUD operations."""

import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from carbon_mesh.db.models import Organization


def _slugify(name: str) -> str:
    """Convert org name to a URL-safe slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "org"


async def create_org(
    session: AsyncSession,
    name: str,
    tier: str = "free",
) -> Organization:
    """Create a new organization."""
    base_slug = _slugify(name)
    slug = base_slug

    # Ensure unique slug
    existing = await session.execute(select(Organization.id).where(Organization.slug == slug))
    if existing.scalar_one_or_none():
        slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

    org = Organization(name=name, slug=slug, tier=tier)
    session.add(org)
    await session.commit()
    await session.refresh(org)
    return org


async def get_org(session: AsyncSession, org_id: str) -> Organization | None:
    result = await session.execute(select(Organization).where(Organization.id == org_id))
    return result.scalar_one_or_none()


async def get_org_by_slug(session: AsyncSession, slug: str) -> Organization | None:
    result = await session.execute(select(Organization).where(Organization.slug == slug))
    return result.scalar_one_or_none()


async def list_orgs(session: AsyncSession) -> list[Organization]:
    result = await session.execute(select(Organization).order_by(Organization.created_at))
    return list(result.scalars().all())
