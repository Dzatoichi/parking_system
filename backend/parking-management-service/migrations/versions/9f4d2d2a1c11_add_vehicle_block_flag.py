"""add vehicle block flag

Revision ID: 9f4d2d2a1c11
Revises: 54ccc166d30b
Create Date: 2026-04-10 23:58:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9f4d2d2a1c11"
down_revision: Union[str, Sequence[str], None] = "54ccc166d30b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "vehicles_table",
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index(op.f("ix_vehicles_table_is_blocked"), "vehicles_table", ["is_blocked"], unique=False)
    op.alter_column("vehicles_table", "is_blocked", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_vehicles_table_is_blocked"), table_name="vehicles_table")
    op.drop_column("vehicles_table", "is_blocked")
