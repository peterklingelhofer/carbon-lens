import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, Integer, String, Boolean, func, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ApiKeyRecord(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    org_name: Mapped[str] = mapped_column(String(255), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    key_prefix: Mapped[str] = mapped_column(String(12), nullable=False)
    tier: Mapped[str] = mapped_column(String(20), nullable=False, default="free")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class EmissionsRecordDB(Base):
    __tablename__ = "emissions_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    api_key_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    chosen_provider: Mapped[str] = mapped_column(String(20), nullable=False)
    chosen_region: Mapped[str] = mapped_column(String(50), nullable=False)
    chosen_grid_zone: Mapped[str] = mapped_column(String(20), nullable=False)
    chosen_carbon_intensity: Mapped[float] = mapped_column(Float, nullable=False)
    worst_carbon_intensity: Mapped[float] = mapped_column(Float, nullable=False)
    carbon_saved_gco2_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    chosen_renewable_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class DailyUsageRecord(Base):
    __tablename__ = "daily_usage"
    __table_args__ = (
        UniqueConstraint("api_key_id", "usage_date", name="uq_daily_usage_key_date"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    api_key_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    usage_date: Mapped[date] = mapped_column(Date, nullable=False)
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
