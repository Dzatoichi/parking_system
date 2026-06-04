from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base


class SegmentsConfig(Base):
    __tablename__ = "segments_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    horizontal_segments: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    vertical_segments: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ParkingContainer(Base):
    __tablename__ = "parking_containers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("camera_table.id", ondelete="CASCADE"), nullable=False, index=True)
    spot_id: Mapped[Optional[int]] = mapped_column(ForeignKey("spots_table.id", ondelete="SET NULL"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    length: Mapped[float] = mapped_column(Float, nullable=False)
    width: Mapped[float] = mapped_column(Float, nullable=False)
    height: Mapped[float] = mapped_column(Float, nullable=False)
    ground_points: Mapped[list] = mapped_column(JSON, nullable=False)
    upper_points: Mapped[list] = mapped_column(JSON, nullable=False)
    image_points: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    is_base: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    camera: Mapped["Cameras"] = relationship("Cameras")
    spot: Mapped[Optional["Spot"]] = relationship("Spot")


class CameraCalibration(Base):
    __tablename__ = "camera_calibrations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    container_id: Mapped[int] = mapped_column(ForeignKey("parking_containers.id", ondelete="CASCADE"), nullable=False, index=True)
    camera_matrix: Mapped[list] = mapped_column(JSON, nullable=False)
    dist_coeffs: Mapped[list] = mapped_column(JSON, nullable=False)
    image_shape: Mapped[list] = mapped_column(JSON, nullable=False)
    rvec: Mapped[list] = mapped_column(JSON, nullable=False)
    tvec: Mapped[list] = mapped_column(JSON, nullable=False)
    homography: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    container: Mapped["ParkingContainer"] = relationship("ParkingContainer")


class CameraConnection(Base):
    __tablename__ = "camera_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    source_camera_id: Mapped[int] = mapped_column(ForeignKey("camera_table.id", ondelete="CASCADE"), nullable=False, index=True)
    source_segment: Mapped[str] = mapped_column(String(30), nullable=False)
    target_camera_id: Mapped[int] = mapped_column(ForeignKey("camera_table.id", ondelete="CASCADE"), nullable=False, index=True)
    target_segment: Mapped[str] = mapped_column(String(30), nullable=False)
    bidirectional: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    weight: Mapped[float] = mapped_column(Float, default=1.0, nullable=False)
    connection_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("source_camera_id", "source_segment", "target_camera_id", "target_segment", name="uq_camera_connection"),
    )


class CVSpotObservation(Base):
    __tablename__ = "cv_spot_observations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False, unique=True)
    parking_id: Mapped[Optional[int]] = mapped_column(ForeignKey("parkings_table.id", ondelete="CASCADE"), nullable=True, index=True)
    camera_id: Mapped[int] = mapped_column(ForeignKey("camera_table.id", ondelete="CASCADE"), nullable=False, index=True)
    spot_id: Mapped[Optional[int]] = mapped_column(ForeignKey("spots_table.id", ondelete="SET NULL"), nullable=True, index=True)
    cv_track_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    bbox: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
