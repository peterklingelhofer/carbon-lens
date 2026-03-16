"""Add ZK broker execution tracking columns.

Revision ID: 0006
Revises: 0005
"""

from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add columns for the full execution pipeline
    op.add_column("zk_jobs", sa.Column("instance_id", sa.String(100), nullable=True))
    op.add_column("zk_jobs", sa.Column("proof_size_bytes", sa.Integer, nullable=False, server_default="0"))
    op.add_column("zk_jobs", sa.Column("verification_tx", sa.String(130), nullable=True))
    op.add_column("zk_jobs", sa.Column("gas_cost_usd", sa.Float, nullable=False, server_default="0"))
    op.add_column("zk_jobs", sa.Column("total_seconds", sa.Float, nullable=False, server_default="0"))
    op.add_column("zk_jobs", sa.Column("started_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("zk_jobs", "started_at")
    op.drop_column("zk_jobs", "total_seconds")
    op.drop_column("zk_jobs", "gas_cost_usd")
    op.drop_column("zk_jobs", "verification_tx")
    op.drop_column("zk_jobs", "proof_size_bytes")
    op.drop_column("zk_jobs", "instance_id")
