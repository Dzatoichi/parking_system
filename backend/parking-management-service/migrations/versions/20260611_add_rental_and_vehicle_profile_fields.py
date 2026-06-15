"""add rental and vehicle profile fields

Revision ID: 20260611_rental_fields
Revises: 20260609_expand_event_type
Create Date: 2026-06-11 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260611_rental_fields"
down_revision: Union[str, Sequence[str], None] = "20260609_expand_event_type"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE spots_table ADD COLUMN IF NOT EXISTS owner_id INTEGER")
    op.execute("ALTER TABLE spots_table ADD COLUMN IF NOT EXISTS rental_enabled BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE spots_table ADD COLUMN IF NOT EXISTS hourly_rate FLOAT NOT NULL DEFAULT 100")
    op.execute("ALTER TABLE spots_table ADD COLUMN IF NOT EXISTS penalty FLOAT NOT NULL DEFAULT 0")
    op.execute("CREATE INDEX IF NOT EXISTS ix_spots_table_owner_id ON spots_table (owner_id)")

    op.execute("ALTER TABLE vehicles_table ADD COLUMN IF NOT EXISTS brand VARCHAR(80)")
    op.execute("ALTER TABLE vehicles_table ADD COLUMN IF NOT EXISTS color VARCHAR(40)")
    op.execute("ALTER TABLE vehicles_table ADD COLUMN IF NOT EXISTS photo_urls JSON")


def downgrade() -> None:
    op.drop_column("vehicles_table", "photo_urls")
    op.drop_column("vehicles_table", "color")
    op.drop_column("vehicles_table", "brand")

    op.drop_index(op.f("ix_spots_table_owner_id"), table_name="spots_table")
    op.drop_column("spots_table", "penalty")
    op.drop_column("spots_table", "hourly_rate")
    op.drop_column("spots_table", "rental_enabled")
    op.drop_column("spots_table", "owner_id")
