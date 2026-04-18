"""add bookings table

Revision ID: 54ccc166d30c
Revises: 9f4d2d2a1c11
Create Date: 2026-04-17 19:40:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "54ccc166d30c"
down_revision: Union[str, Sequence[str], None] = "9f4d2d2a1c11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    op.execute(
        """
        DO $$
        BEGIN
            CREATE TYPE bookingstatus AS ENUM (
                'PENDING',
                'CONFIRMED',
                'CANCELLED',
                'COMPLETED',
                'EXPIRED'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END
        $$;
        """
    )

    if inspector.has_table("bookings"):
        op.execute("CREATE INDEX IF NOT EXISTS ix_bookings_id ON bookings (id)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_bookings_user_id ON bookings (user_id)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_bookings_spot_id ON bookings (spot_id)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_bookings_status ON bookings (status)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_bookings_start_time ON bookings (start_time)")
        op.execute("CREATE INDEX IF NOT EXISTS ix_bookings_end_time ON bookings (end_time)")
        return

    op.create_table(
        "bookings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("spot_id", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PENDING",
                "CONFIRMED",
                "CANCELLED",
                "COMPLETED",
                "EXPIRED",
                name="bookingstatus",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("notes", sa.String(length=500), nullable=True),
        sa.Column("cancellation_reason", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["spot_id"], ["spots_table.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_bookings_id"), "bookings", ["id"], unique=False)
    op.create_index(op.f("ix_bookings_user_id"), "bookings", ["user_id"], unique=False)
    op.create_index(op.f("ix_bookings_spot_id"), "bookings", ["spot_id"], unique=False)
    op.create_index(op.f("ix_bookings_status"), "bookings", ["status"], unique=False)
    op.create_index(op.f("ix_bookings_start_time"), "bookings", ["start_time"], unique=False)
    op.create_index(op.f("ix_bookings_end_time"), "bookings", ["end_time"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_bookings_end_time"), table_name="bookings")
    op.drop_index(op.f("ix_bookings_start_time"), table_name="bookings")
    op.drop_index(op.f("ix_bookings_status"), table_name="bookings")
    op.drop_index(op.f("ix_bookings_spot_id"), table_name="bookings")
    op.drop_index(op.f("ix_bookings_user_id"), table_name="bookings")
    op.drop_index(op.f("ix_bookings_id"), table_name="bookings")
    op.drop_table("bookings")
    op.execute("DROP TYPE IF EXISTS bookingstatus")
