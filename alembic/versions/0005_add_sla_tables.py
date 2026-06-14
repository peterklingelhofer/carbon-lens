"""Add Green SLA tables for durable definitions, checks, and reports.

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
        "green_slas",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("org_id", sa.String(36), nullable=False, index=True),
        sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true(), index=True),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("payload", sa.Text, nullable=False),
    )

    op.create_table(
        "sla_checks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("sla_id", sa.String(36), nullable=False, index=True),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("payload", sa.Text, nullable=False),
    )

    op.create_table(
        "sla_reports",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("sla_id", sa.String(36), nullable=False, index=True),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.Text, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("sla_reports")
    op.drop_table("sla_checks")
    op.drop_table("green_slas")
