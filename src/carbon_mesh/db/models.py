import uuid
from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Boolean, func, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Organization(Base):
    """Multi-tenant organization — all API keys and usage are scoped to an org."""

    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    tier: Mapped[str] = mapped_column(String(20), nullable=False, default="free")
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), nullable=True, unique=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    api_keys: Mapped[list["ApiKeyRecord"]] = relationship(back_populates="organization")


class ApiKeyRecord(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    org_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=True, index=True
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

    organization: Mapped[Organization | None] = relationship(back_populates="api_keys")


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


# --- Compliance / Emissions tables ---


class CloudUsageRecordDB(Base):
    """Stores ingested cloud usage data from AWS/GCP/Azure billing."""

    __tablename__ = "cloud_usage_records"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    region: Mapped[str] = mapped_column(String(50), nullable=False)
    service: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
    usage_quantity: Mapped[float] = mapped_column(Float, nullable=False)
    usage_unit: Mapped[str] = mapped_column(String(30), nullable=False)
    energy_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )


class EmissionsCalculationDB(Base):
    """Stores individual emissions calculations with full audit trail."""

    __tablename__ = "emissions_calculations"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    scope: Mapped[str] = mapped_column(String(20), nullable=False)  # scope_2, scope_3_cat1
    method: Mapped[str] = mapped_column(String(20), nullable=False)  # location_based, market_based
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    region: Mapped[str] = mapped_column(String(50), nullable=False)
    grid_zone: Mapped[str] = mapped_column(String(30), nullable=False)
    service: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    usage_quantity: Mapped[float] = mapped_column(Float, nullable=False)
    usage_unit: Mapped[str] = mapped_column(String(30), nullable=False)
    energy_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    emission_factor_gco2_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    emission_factor_source: Mapped[str] = mapped_column(String(50), nullable=False)
    emission_factor_quality: Mapped[str] = mapped_column(String(20), nullable=False)
    emissions_kgco2e: Mapped[float] = mapped_column(Float, nullable=False)
    renewable_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    pue: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    methodology_version: Mapped[str] = mapped_column(String(50), nullable=False, default="ghg_protocol_2024")


class ComplianceReportDB(Base):
    """Stores generated compliance reports for audit trail."""

    __tablename__ = "compliance_reports"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    org_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organizations.id"), nullable=False, index=True
    )
    report_name: Mapped[str] = mapped_column(String(255), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    total_kgco2e: Mapped[float] = mapped_column(Float, nullable=False)
    total_energy_kwh: Mapped[float] = mapped_column(Float, nullable=False)
    avg_renewable_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    carbon_saved_kgco2e: Mapped[float] = mapped_column(Float, nullable=False)
    carbon_saved_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    scope2_location_kgco2e: Mapped[float] = mapped_column(Float, nullable=False)
    scope2_market_kgco2e: Mapped[float] = mapped_column(Float, nullable=False)
    scope3_cat1_kgco2e: Mapped[float] = mapped_column(Float, nullable=False)
    calculation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    methodology: Mapped[str] = mapped_column(String(255), nullable=False)
    reporting_standard: Mapped[str] = mapped_column(String(100), nullable=False, default="CSRD / ESRS E1")
    report_json: Mapped[str | None] = mapped_column(nullable=True)  # Full report as JSON for export
