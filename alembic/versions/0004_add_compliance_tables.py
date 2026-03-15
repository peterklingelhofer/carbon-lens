"""Add compliance tables for cloud usage, emissions calculations, and reports.

Revision ID: 0004
Revises: 0003
"""

from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cloud_usage_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("region", sa.String(50), nullable=False),
        sa.Column("service", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False, server_default="default"),
        sa.Column("usage_quantity", sa.Float, nullable=False),
        sa.Column("usage_unit", sa.String(30), nullable=False),
        sa.Column("energy_kwh", sa.Float, nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(30), nullable=False, server_default="manual"),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "emissions_calculations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("region", sa.String(50), nullable=False),
        sa.Column("grid_zone", sa.String(30), nullable=False),
        sa.Column("service", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=False),
        sa.Column("usage_quantity", sa.Float, nullable=False),
        sa.Column("usage_unit", sa.String(30), nullable=False),
        sa.Column("energy_kwh", sa.Float, nullable=False),
        sa.Column("emission_factor_gco2_kwh", sa.Float, nullable=False),
        sa.Column("emission_factor_source", sa.String(50), nullable=False),
        sa.Column("emission_factor_quality", sa.String(20), nullable=False),
        sa.Column("emissions_kgco2e", sa.Float, nullable=False),
        sa.Column("renewable_percentage", sa.Float, nullable=False),
        sa.Column("pue", sa.Float, nullable=False, server_default="1.0"),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("methodology_version", sa.String(50), nullable=False, server_default="ghg_protocol_2024"),
    )

    op.create_table(
        "compliance_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False, index=True),
        sa.Column("report_name", sa.String(255), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("total_kgco2e", sa.Float, nullable=False),
        sa.Column("total_energy_kwh", sa.Float, nullable=False),
        sa.Column("avg_renewable_percentage", sa.Float, nullable=False),
        sa.Column("carbon_saved_kgco2e", sa.Float, nullable=False),
        sa.Column("carbon_saved_percentage", sa.Float, nullable=False),
        sa.Column("scope2_location_kgco2e", sa.Float, nullable=False),
        sa.Column("scope2_market_kgco2e", sa.Float, nullable=False),
        sa.Column("scope3_cat1_kgco2e", sa.Float, nullable=False),
        sa.Column("calculation_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("methodology", sa.String(255), nullable=False),
        sa.Column("reporting_standard", sa.String(100), nullable=False, server_default="CSRD / ESRS E1"),
        sa.Column("report_json", sa.Text, nullable=True),
    )


def downgrade() -> None:
    op.drop_table("compliance_reports")
    op.drop_table("emissions_calculations")
    op.drop_table("cloud_usage_records")
