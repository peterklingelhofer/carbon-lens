import secrets

from fastapi import Depends, HTTPException, Query, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from carbonlens.api.deps import get_session
from carbonlens.config import settings
from carbonlens.db.models import ApiKeyRecord

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def _get_session_for_auth():
    # No key validation needed -> no session needed. Otherwise reuse the shared
    # request-scoped session dependency (which yields None when no DB is configured)
    if not settings.api_key_required:
        yield None
        return
    async for session in get_session():
        yield session


async def require_api_key(
    api_key: str | None = Security(api_key_header),
    session: AsyncSession | None = Depends(_get_session_for_auth),
) -> ApiKeyRecord | None:
    if not settings.api_key_required:
        return None

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API key. Pass it via X-API-Key header.",
        )

    if session is None:
        raise HTTPException(
            status_code=503,
            detail="Database not configured. Cannot validate API keys.",
        )

    from carbonlens.auth.api_keys import validate_api_key

    record = await validate_api_key(session, api_key)
    if record is None:
        raise HTTPException(status_code=403, detail="Invalid or revoked API key.")
    return record


def resolve_org_id(key: ApiKeyRecord | None, org_id: str) -> str:
    """Reconcile a client-supplied org_id with the authenticated key's own org.

    A key's org always wins: a client-supplied org_id that disagrees with it gets
    a 403, which keeps one org's key scoped to reading and writing only that
    org's data. With keys off, or a key that isn't tied to any org, org_id is
    trusted as given, keeping the keyless demo mode unchanged.
    """
    if key is not None and key.org_id is not None:
        if org_id != key.org_id:
            raise HTTPException(
                status_code=403,
                detail="org_id does not match the authenticated API key's organization.",
            )
        return key.org_id
    return org_id


async def require_org_id(
    org_id: str = Query(...),
    key: ApiKeyRecord | None = Depends(require_api_key),
) -> str:
    """Query-param org scoping: drop-in replacement for `org_id: str = Query(...)`
    that resolves to the authenticated key's org (or 403s on a mismatch)."""
    return resolve_org_id(key=key, org_id=org_id)


async def require_admin(
    api_key: str | None = Security(api_key_header),
) -> None:
    if not settings.admin_secret:
        raise HTTPException(status_code=503, detail="Admin endpoint not configured.")
    if not api_key or not secrets.compare_digest(api_key, settings.admin_secret):
        raise HTTPException(status_code=403, detail="Invalid admin secret.")
