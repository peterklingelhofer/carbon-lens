"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-03-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "api_keys",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_name", sa.String(255), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("key_prefix", sa.String(12), nullable=False),
        sa.Column("tier", sa.String(20), nullable=False, server_default="free"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_api_keys_key_hash", "api_keys", ["key_hash"])

    op.create_table(
        "emissions_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("request_id", sa.String(36), nullable=False),
        sa.Column("api_key_id", sa.String(36), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("chosen_provider", sa.String(20), nullable=False),
        sa.Column("chosen_region", sa.String(50), nullable=False),
        sa.Column("chosen_grid_zone", sa.String(20), nullable=False),
        sa.Column("chosen_carbon_intensity", sa.Float, nullable=False),
        sa.Column("worst_carbon_intensity", sa.Float, nullable=False),
        sa.Column("carbon_saved_gco2_kwh", sa.Float, nullable=False),
        sa.Column("chosen_renewable_pct", sa.Float, nullable=False, server_default="0"),
    )
    op.create_index("ix_emissions_records_request_id", "emissions_records", ["request_id"])
    op.create_index("ix_emissions_records_api_key_id", "emissions_records", ["api_key_id"])


def downgrade() -> None:
    op.drop_table("emissions_records")
    op.drop_table("api_keys")
