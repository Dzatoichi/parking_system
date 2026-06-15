from datetime import datetime
from typing import Optional

import numpy as np

from src.database.base import Base
from sqlalchemy import Integer, String, ForeignKey, Boolean, JSON
from sqlalchemy.orm import mapped_column, Mapped, relationship
from pgvector.sqlalchemy import Vector


class Vehicles(Base):
    __tablename__ = "vehicles_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    plate_number: Mapped[str] = mapped_column(String(12), unique=True, index=True, nullable=False)
    features: Mapped[np.ndarray] = mapped_column(
        Vector(512),
        nullable=True,
        comment="Вектор признаков автомобиля",
    )
    is_inside: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    last_seen: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    last_camera_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("camera_table.id", ondelete="SET NULL"),
        nullable=True,
    )
    # ID владельца
    owner_id: Mapped[int] = mapped_column( Integer, nullable=False, index=True)
    brand: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    photo_urls: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Текущее парковочное место (если есть)
    current_spot: Mapped[Optional["Spot"]] = relationship(
        "Spot",
        back_populates="current_vehicle",
        foreign_keys="Spot.current_vehicle_id",
    )

    # История перемещений
    tracking_history: Mapped[list["Tracking"]] = relationship(
        "Tracking",
        back_populates="vehicle",
        cascade="all, delete-orphan",
    )
