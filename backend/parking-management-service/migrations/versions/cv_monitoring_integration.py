"""cv monitoring integration

Revision ID: cv_monitoring_integration
Revises: b7f2b9b6c1a0
Create Date: 2026-05-20 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "cv_monitoring_integration"
down_revision: Union[str, Sequence[str], None] = "b7f2b9b6c1a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "segments_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("horizontal_segments", sa.Integer(), nullable=False, server_default="8"),
        sa.Column("vertical_segments", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_segments_configs_id"), "segments_configs", ["id"], unique=False)

    op.add_column("camera_table", sa.Column("segments_config_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_camera_table_segments_config_id",
        "camera_table",
        "segments_configs",
        ["segments_config_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("bookings", sa.Column("vehicle_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_bookings_vehicle_id"), "bookings", ["vehicle_id"], unique=False)
    op.create_foreign_key(
        "fk_bookings_vehicle_id",
        "bookings",
        "vehicles_table",
        ["vehicle_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("booking_projection", sa.Column("vehicle_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_booking_projection_vehicle_id"), "booking_projection", ["vehicle_id"], unique=False)

    op.create_table(
        "parking_containers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("camera_id", sa.Integer(), nullable=False),
        sa.Column("spot_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("length", sa.Float(), nullable=False),
        sa.Column("width", sa.Float(), nullable=False),
        sa.Column("height", sa.Float(), nullable=False),
        sa.Column("ground_points", sa.JSON(), nullable=False),
        sa.Column("upper_points", sa.JSON(), nullable=False),
        sa.Column("image_points", sa.JSON(), nullable=True),
        sa.Column("is_base", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["camera_id"], ["camera_table.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["spot_id"], ["spots_table.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_parking_containers_camera_id"), "parking_containers", ["camera_id"], unique=False)
    op.create_index(op.f("ix_parking_containers_id"), "parking_containers", ["id"], unique=False)
    op.create_index(op.f("ix_parking_containers_spot_id"), "parking_containers", ["spot_id"], unique=False)

    op.create_table(
        "camera_calibrations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("container_id", sa.Integer(), nullable=False),
        sa.Column("camera_matrix", sa.JSON(), nullable=False),
        sa.Column("dist_coeffs", sa.JSON(), nullable=False),
        sa.Column("image_shape", sa.JSON(), nullable=False),
        sa.Column("rvec", sa.JSON(), nullable=False),
        sa.Column("tvec", sa.JSON(), nullable=False),
        sa.Column("homography", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["container_id"], ["parking_containers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_camera_calibrations_container_id"), "camera_calibrations", ["container_id"], unique=False)
    op.create_index(op.f("ix_camera_calibrations_id"), "camera_calibrations", ["id"], unique=False)

    op.create_table(
        "camera_connections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("source_camera_id", sa.Integer(), nullable=False),
        sa.Column("source_segment", sa.String(length=30), nullable=False),
        sa.Column("target_camera_id", sa.Integer(), nullable=False),
        sa.Column("target_segment", sa.String(length=30), nullable=False),
        sa.Column("bidirectional", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("weight", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("connection_metadata", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["source_camera_id"], ["camera_table.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_camera_id"], ["camera_table.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_camera_id", "source_segment", "target_camera_id", "target_segment", name="uq_camera_connection"),
    )
    op.create_index(op.f("ix_camera_connections_id"), "camera_connections", ["id"], unique=False)
    op.create_index(op.f("ix_camera_connections_source_camera_id"), "camera_connections", ["source_camera_id"], unique=False)
    op.create_index(op.f("ix_camera_connections_target_camera_id"), "camera_connections", ["target_camera_id"], unique=False)

    op.create_table(
        "cv_spot_observations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("event_id", sa.String(length=36), nullable=False),
        sa.Column("parking_id", sa.Integer(), nullable=True),
        sa.Column("camera_id", sa.Integer(), nullable=False),
        sa.Column("spot_id", sa.Integer(), nullable=True),
        sa.Column("cv_track_id", sa.String(length=100), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("bbox", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["camera_id"], ["camera_table.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parking_id"], ["parkings_table.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["spot_id"], ["spots_table.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_id"),
    )
    op.create_index(op.f("ix_cv_spot_observations_camera_id"), "cv_spot_observations", ["camera_id"], unique=False)
    op.create_index(op.f("ix_cv_spot_observations_cv_track_id"), "cv_spot_observations", ["cv_track_id"], unique=False)
    op.create_index(op.f("ix_cv_spot_observations_event_type"), "cv_spot_observations", ["event_type"], unique=False)
    op.create_index(op.f("ix_cv_spot_observations_id"), "cv_spot_observations", ["id"], unique=False)
    op.create_index(op.f("ix_cv_spot_observations_observed_at"), "cv_spot_observations", ["observed_at"], unique=False)
    op.create_index(op.f("ix_cv_spot_observations_parking_id"), "cv_spot_observations", ["parking_id"], unique=False)
    op.create_index(op.f("ix_cv_spot_observations_spot_id"), "cv_spot_observations", ["spot_id"], unique=False)


def downgrade() -> None:
    op.drop_table("cv_spot_observations")
    op.drop_table("camera_connections")
    op.drop_table("camera_calibrations")
    op.drop_table("parking_containers")
    op.drop_index(op.f("ix_booking_projection_vehicle_id"), table_name="booking_projection")
    op.drop_column("booking_projection", "vehicle_id")
    op.drop_constraint("fk_bookings_vehicle_id", "bookings", type_="foreignkey")
    op.drop_index(op.f("ix_bookings_vehicle_id"), table_name="bookings")
    op.drop_column("bookings", "vehicle_id")
    op.drop_constraint("fk_camera_table_segments_config_id", "camera_table", type_="foreignkey")
    op.drop_column("camera_table", "segments_config_id")
    op.drop_index(op.f("ix_segments_configs_id"), table_name="segments_configs")
    op.drop_table("segments_configs")
