import hashlib
import secrets
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from carbon_mesh.db.models import ApiKeyRecord

PREFIX = "cmesh_"


def generate_api_key() -> str:
    return PREFIX + secrets.token_hex(24)


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def key_prefix(raw_key: str) -> str:
    return raw_key[: len(PREFIX) + 4] + "..."


async def create_api_key(
    session: AsyncSession,
    org_name: str,
    tier: str = "free",
) -> tuple[ApiKeyRecord, str]:
    raw_key = generate_api_key()
    record = ApiKeyRecord(
        org_name=org_name,
        key_hash=hash_key(raw_key),
        key_prefix=key_prefix(raw_key),
        tier=tier,
    )
    session.add(record)
    await session.commit()
    await session.refresh(record)
    return record, raw_key


async def validate_api_key(session: AsyncSession, raw_key: str) -> ApiKeyRecord | None:
    if not raw_key.startswith(PREFIX):
        return None
    hashed = hash_key(raw_key)
    stmt = select(ApiKeyRecord).where(
        ApiKeyRecord.key_hash == hashed,
        ApiKeyRecord.is_active.is_(True),
    )
    result = await session.execute(stmt)
    record = result.scalar_one_or_none()
    if record:
        await session.execute(
            update(ApiKeyRecord)
            .where(ApiKeyRecord.id == record.id)
            .values(last_used_at=datetime.now(UTC))
        )
        await session.commit()
    return record
