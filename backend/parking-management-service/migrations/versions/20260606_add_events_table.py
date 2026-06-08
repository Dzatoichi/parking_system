"""add events table

Revision ID: 20260606_add_events_table
Revises: 20260605_sergey_monitor_runtime
Create Date: 2026-06-06 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260606_add_events_table"
down_revision: Union[str, Sequence[str], None] = "20260605_sergey_monitor_runtime"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "events_table",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_type", sa.String(length=15), nullable=False),
        sa.Column("entity_type", sa.String(length=15), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("parking_id", sa.Integer(), nullable=False),
        sa.Column("message", sa.String(length=30), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["parking_id"], ["parkings_table.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_events_table_entity_id"), "events_table", ["entity_id"], unique=False)
    op.create_index(op.f("ix_events_table_id"), "events_table", ["id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_events_table_id"), table_name="events_table")
    op.drop_index(op.f("ix_events_table_entity_id"), table_name="events_table")
    op.drop_table("events_table")
