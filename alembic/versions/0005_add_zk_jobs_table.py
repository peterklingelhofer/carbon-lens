"""Add ZK broker jobs table.

Revision ID: 0005
Revises: 0004
"""

from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "zk_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=True, index=True),
        sa.Column("network", sa.String(30), nullable=False),
        sa.Column("proof_system", sa.String(20), nullable=False),
        sa.Column("circuit_size", sa.Integer, nullable=False),
        sa.Column("bounty_usd", sa.Float, nullable=False),
        sa.Column("bounty_token", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, index=True),
        sa.Column("compute_provider", sa.String(30), nullable=True),
        sa.Column("compute_region", sa.String(50), nullable=True),
        sa.Column("gpu_type", sa.String(20), nullable=True),
        sa.Column("grid_zone", sa.String(30), nullable=True),
        sa.Column("compute_cost_usd", sa.Float, nullable=False, server_default="0"),
        sa.Column("bounty_earned_usd", sa.Float, nullable=False, server_default="0"),
        sa.Column("profit_usd", sa.Float, nullable=False, server_default="0"),
        sa.Column("carbon_grams_co2", sa.Float, nullable=False, server_default="0"),
        sa.Column("renewable_percentage", sa.Float, nullable=False, server_default="0"),
        sa.Column("carbon_intensity_gco2_kwh", sa.Float, nullable=False, server_default="0"),
        sa.Column("gpu_seconds", sa.Float, nullable=False, server_default="0"),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("proof_hash", sa.String(130), nullable=True),
        sa.Column("error", sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("zk_jobs")
