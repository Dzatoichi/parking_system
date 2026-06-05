"""sergey monitor runtime tables

Revision ID: 20260605_sergey_monitor_runtime
Revises: cv_monitoring_integration
Create Date: 2026-06-05 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260605_sergey_monitor_runtime"
down_revision: Union[str, Sequence[str], None] = "cv_monitoring_integration"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "parking_spots_current",
        sa.Column("spot_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="free"),
        sa.Column("vehicle_track_id", sa.Integer(), nullable=True),
        sa.Column("parked_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_updated", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["spot_id"], ["parking_containers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("spot_id"),
    )
    op.create_index("idx_parking_spots_status", "parking_spots_current", ["status"])

    op.create_table(
        "spot_occupancy",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("spot_id", sa.Integer(), nullable=False),
        sa.Column("vehicle_track_id", sa.Integer(), nullable=False),
        sa.Column("occupied_since", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("occupied_until", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["spot_id"], ["parking_containers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_occupancy_current", "spot_occupancy", ["spot_id"], postgresql_where=sa.text("occupied_until IS NULL"))
    op.create_index("idx_occupancy_spot_time", "spot_occupancy", ["spot_id", "occupied_since"])
    op.create_index(
        "idx_occupancy_vehicle",
        "spot_occupancy",
        ["vehicle_track_id"],
        postgresql_where=sa.text("occupied_until IS NULL"),
    )

    op.execute(
        """
        CREATE OR REPLACE VIEW cameras AS
        SELECT
            c.id,
            c.rtsp_url AS video_path,
            ('Camera ' || c.id::text)::varchar(100) AS name,
            ('Parking ' || c.parking_id::text)::varchar(200) AS location,
            COALESCE(
                c.segments_config_id,
                (SELECT sc.id FROM segments_configs sc ORDER BY sc.id LIMIT 1),
                1
            ) AS segments_config_id,
            (c.status::text IN ('ACTIVE', 'active')) AS is_active,
            NOW() AS created_at,
            NOW() AS updated_at
        FROM camera_table c
        """
    )
    op.execute(
        """
        CREATE OR REPLACE VIEW camera_calibration AS
        SELECT
            id,
            container_id,
            camera_matrix,
            rvec,
            tvec,
            dist_coeffs,
            image_shape,
            created_at,
            homography
        FROM camera_calibrations
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION sync_cv_spot_current_to_spots()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            UPDATE spots_table s
            SET
                spot_status = CASE
                    WHEN NEW.status = 'occupied' THEN 'OCCUPIED'
                    WHEN s.spot_status = 'RESERVED' THEN s.spot_status
                    ELSE 'FREE'
                END,
                occupied_since = CASE
                    WHEN NEW.status = 'occupied' THEN NEW.parked_since
                    ELSE NULL
                END
            FROM parking_containers pc
            WHERE pc.id = NEW.spot_id
              AND pc.spot_id = s.id;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_sync_cv_spot_current_to_spots
        AFTER INSERT OR UPDATE ON parking_spots_current
        FOR EACH ROW
        EXECUTE FUNCTION sync_cv_spot_current_to_spots()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_sync_cv_spot_current_to_spots ON parking_spots_current")
    op.execute("DROP FUNCTION IF EXISTS sync_cv_spot_current_to_spots()")
    op.execute("DROP VIEW IF EXISTS camera_calibration")
    op.execute("DROP VIEW IF EXISTS cameras")
    op.drop_index("idx_occupancy_vehicle", table_name="spot_occupancy")
    op.drop_index("idx_occupancy_spot_time", table_name="spot_occupancy")
    op.drop_index("idx_occupancy_current", table_name="spot_occupancy")
    op.drop_table("spot_occupancy")
    op.drop_index("idx_parking_spots_status", table_name="parking_spots_current")
    op.drop_table("parking_spots_current")
