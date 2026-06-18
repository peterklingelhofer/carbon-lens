"""add impact_records table

The org system-of-record for carbon-aware run impact: hosts POST one row per run,
so `org-statement` can be served live and multi-host instead of gathering ledger
files. Used only when a database is configured.

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-18
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "impact_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("api_key_id", sa.String(36), nullable=True),
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("region", sa.String(64), nullable=False),
        sa.Column("deferred_hours", sa.Integer, nullable=False, server_default="0"),
        sa.Column("reduction_gco2_kwh", sa.Float, nullable=False, server_default="0"),
        sa.Column("energy_kwh", sa.Float, nullable=True),
        sa.Column("basis", sa.String(16), nullable=False, server_default="forecast"),
    )
    op.create_index("ix_impact_records_ts", "impact_records", ["ts"])
    op.create_index("ix_impact_records_api_key_id", "impact_records", ["api_key_id"])


def downgrade() -> None:
    op.drop_table("impact_records")
