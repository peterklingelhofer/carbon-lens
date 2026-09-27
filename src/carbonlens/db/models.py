import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ApiKeyRecord(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # No ForeignKey here: the live "organizations" table (see alembic/versions/
    # 0003_add_organizations_and_stripe.py) has no corresponding ORM model since
    # nothing reads or writes it, so a FK to it can't resolve against Base.metadata
    org_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
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

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    api_key_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    chosen_provider: Mapped[str] = mapped_column(String(20), nullable=False)
    chosen_region: Mapped[str] = mapped_column(String(50), nullable=False)
    chosen_grid_zone: Mapped[str] = mapped_column(String(20), nullable=False)
    chosen_carbon_intensity: Mapped[float] = mapped_column(Float, nullable=False)
    baseline_carbon_intensity: Mapped[float] = mapped_column(Float, nullable=False)
    intensity_reduction_gco2_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    chosen_renewable_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)


class ImpactRecordDB(Base):
    """One carbon-aware run's record: the org system-of-record for `carbonlens run`
    impact. Hosts POST here when configured, so org-statement is live and multi-host
    instead of a manual ledger-file gather."""

    __tablename__ = "impact_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    api_key_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
        index=True,
    )
    region: Mapped[str] = mapped_column(String(64), nullable=False)
    deferred_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reduction_gco2_kwh: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    energy_kwh: Mapped[float | None] = mapped_column(Float, nullable=True)
    basis: Mapped[str] = mapped_column(String(16), nullable=False, default="forecast")


# --- Green SLA tables ---
# Each row stores its domain model as JSON (payload) plus a few indexed columns
# for querying. The nested shape (breached_regions, checks_by_day, ...) round-trips
# losslessly via pydantic, so the schema stays stable as those details evolve


class GreenSLADB(Base):
    """A persisted Green SLA definition."""

    __tablename__ = "green_slas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    org_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(UTC)
    )
    payload: Mapped[str] = mapped_column(Text, nullable=False)


class SLACheckDB(Base):
    """A persisted SLA compliance check result."""

    __tablename__ = "sla_checks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    sla_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    payload: Mapped[str] = mapped_column(Text, nullable=False)


class SLAReportDB(Base):
    """A persisted SLA attestation report."""

    __tablename__ = "sla_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    sla_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    payload: Mapped[str] = mapped_column(Text, nullable=False)
