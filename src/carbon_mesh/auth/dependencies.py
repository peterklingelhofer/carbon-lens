import secrets

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from carbon_mesh.config import settings
from carbon_mesh.db.models import ApiKeyRecord

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def _get_session_for_auth():
    if not settings.use_database or not settings.api_key_required:
        yield None
        return
    from carbon_mesh.db.engine import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
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

    from carbon_mesh.auth.api_keys import validate_api_key

    record = await validate_api_key(session, api_key)
    if record is None:
        raise HTTPException(status_code=403, detail="Invalid or revoked API key.")
    return record


async def require_admin(
    api_key: str | None = Security(api_key_header),
) -> None:
    if not settings.admin_secret:
        raise HTTPException(status_code=503, detail="Admin endpoint not configured.")
    if not api_key or not secrets.compare_digest(api_key, settings.admin_secret):
        raise HTTPException(status_code=403, detail="Invalid admin secret.")
