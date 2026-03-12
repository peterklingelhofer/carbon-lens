"""add daily usage table

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-12
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "daily_usage",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("api_key_id", sa.String(36), nullable=False),
        sa.Column("usage_date", sa.Date, nullable=False),
        sa.Column("request_count", sa.Integer, nullable=False, server_default="0"),
        sa.UniqueConstraint("api_key_id", "usage_date", name="uq_daily_usage_key_date"),
    )
    op.create_index("ix_daily_usage_api_key_id", "daily_usage", ["api_key_id"])


def downgrade() -> None:
    op.drop_table("daily_usage")
