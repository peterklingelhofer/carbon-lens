"""rename emissions savings columns to an honest baseline

Renames the routing-savings columns to reflect an honest counterfactual:
worst_carbon_intensity -> baseline_carbon_intensity (mean of candidates, not the
single worst), and carbon_saved_gco2_kwh -> intensity_reduction_gco2_kwh (a rate,
which is not additive across workloads).

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-16
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "emissions_records", "worst_carbon_intensity", new_column_name="baseline_carbon_intensity"
    )
    op.alter_column(
        "emissions_records", "carbon_saved_gco2_kwh", new_column_name="intensity_reduction_gco2_kwh"
    )


def downgrade() -> None:
    op.alter_column(
        "emissions_records", "baseline_carbon_intensity", new_column_name="worst_carbon_intensity"
    )
    op.alter_column(
        "emissions_records", "intensity_reduction_gco2_kwh", new_column_name="carbon_saved_gco2_kwh"
    )
