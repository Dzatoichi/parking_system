"""expand events event_type length

Revision ID: 20260609_expand_event_type
Revises: 20260606_add_events_table
Create Date: 2026-06-09 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260609_expand_event_type"
down_revision: Union[str, Sequence[str], None] = "20260606_add_events_table"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "events_table",
        "event_type",
        existing_type=sa.String(length=15),
        type_=sa.String(length=50),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "events_table",
        "event_type",
        existing_type=sa.String(length=50),
        type_=sa.String(length=15),
        existing_nullable=False,
    )
