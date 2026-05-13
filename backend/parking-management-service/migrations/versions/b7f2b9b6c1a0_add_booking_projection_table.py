"""add booking projection table

Revision ID: b7f2b9b6c1a0
Revises: 0a6e880e868d
Create Date: 2026-05-13 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "b7f2b9b6c1a0"
down_revision = "0a6e880e868d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "booking_projection",
        sa.Column("booking_id", sa.Integer(), nullable=False),
        sa.Column("parking_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("user_name", sa.String(length=255), nullable=True),
        sa.Column("spot_id", sa.Integer(), nullable=False),
        sa.Column("spot_number", sa.String(length=10), nullable=False),
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
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("booking_id"),
    )
    op.create_index(op.f("ix_booking_projection_created_at"), "booking_projection", ["created_at"], unique=False)
    op.create_index(op.f("ix_booking_projection_parking_id"), "booking_projection", ["parking_id"], unique=False)
    op.create_index(op.f("ix_booking_projection_spot_id"), "booking_projection", ["spot_id"], unique=False)
    op.create_index(op.f("ix_booking_projection_status"), "booking_projection", ["status"], unique=False)
    op.create_index(op.f("ix_booking_projection_user_id"), "booking_projection", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_booking_projection_user_id"), table_name="booking_projection")
    op.drop_index(op.f("ix_booking_projection_status"), table_name="booking_projection")
    op.drop_index(op.f("ix_booking_projection_spot_id"), table_name="booking_projection")
    op.drop_index(op.f("ix_booking_projection_parking_id"), table_name="booking_projection")
    op.drop_index(op.f("ix_booking_projection_created_at"), table_name="booking_projection")
    op.drop_table("booking_projection")
