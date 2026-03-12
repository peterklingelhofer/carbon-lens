from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from carbon_mesh.auth.api_keys import create_api_key
from carbon_mesh.auth.dependencies import require_admin
from carbon_mesh.db.engine import get_session

admin_router = APIRouter(prefix="/admin", tags=["Admin"], dependencies=[Depends(require_admin)])


class CreateKeyRequest(BaseModel):
    org_name: str
    tier: str = "free"


class CreateKeyResponse(BaseModel):
    api_key: str
    key_prefix: str
    org_name: str
    tier: str
    message: str = "Store this key securely — it will not be shown again."


@admin_router.post("/api-keys", response_model=CreateKeyResponse)
async def create_key(
    body: CreateKeyRequest,
    session: AsyncSession = Depends(get_session),
) -> CreateKeyResponse:
    """Create a new API key for an organization."""
    record, raw_key = await create_api_key(session, body.org_name, body.tier)
    return CreateKeyResponse(
        api_key=raw_key,
        key_prefix=record.key_prefix,
        org_name=record.org_name,
        tier=record.tier,
    )
