"""add organizations table and stripe fields

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-13
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Organizations table
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("tier", sa.String(20), nullable=False, server_default="free"),
        sa.Column("stripe_customer_id", sa.String(255), nullable=True, unique=True),
        sa.Column("stripe_subscription_id", sa.String(255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_organizations_slug", "organizations", ["slug"])

    # Add org_id FK to api_keys
    op.add_column(
        "api_keys",
        sa.Column("org_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=True),
    )
    op.create_index("ix_api_keys_org_id", "api_keys", ["org_id"])


def downgrade() -> None:
    op.drop_index("ix_api_keys_org_id", table_name="api_keys")
    op.drop_column("api_keys", "org_id")
    op.drop_table("organizations")
