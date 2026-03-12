"""Usage tracking and tier limit enforcement."""

from datetime import date

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from carbon_mesh.billing.models import TIERS, BillingStatus
from carbon_mesh.db.models import ApiKeyRecord, DailyUsageRecord


async def get_today_usage(session: AsyncSession, api_key_id: str) -> int:
    today = date.today()
    stmt = select(DailyUsageRecord.request_count).where(
        DailyUsageRecord.api_key_id == api_key_id,
        DailyUsageRecord.usage_date == today,
    )
    result = await session.execute(stmt)
    count = result.scalar_one_or_none()
    return count or 0


async def increment_usage(session: AsyncSession, api_key_id: str) -> int:
    today = date.today()

    # Try to increment existing record
    stmt = (
        update(DailyUsageRecord)
        .where(
            DailyUsageRecord.api_key_id == api_key_id,
            DailyUsageRecord.usage_date == today,
        )
        .values(request_count=DailyUsageRecord.request_count + 1)
        .returning(DailyUsageRecord.request_count)
    )
    result = await session.execute(stmt)
    row = result.scalar_one_or_none()

    if row is not None:
        await session.commit()
        return row

    # Create new record for today
    record = DailyUsageRecord(
        api_key_id=api_key_id,
        usage_date=today,
        request_count=1,
    )
    session.add(record)
    await session.commit()
    return 1


async def check_usage_limit(session: AsyncSession, api_key: ApiKeyRecord) -> BillingStatus:
    tier_info = TIERS.get(api_key.tier, TIERS["free"])
    today_usage = await get_today_usage(session, api_key.id)

    return BillingStatus(
        api_key_id=api_key.id,
        tier=api_key.tier,
        plan=tier_info,
        today_usage=today_usage,
        daily_limit=tier_info.daily_limit,
        remaining=max(0, tier_info.daily_limit - today_usage),
    )


def is_over_limit(status: BillingStatus) -> bool:
    return status.today_usage >= status.daily_limit
