from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, ForeignKey, DateTime, JSON, Index
from datetime import datetime
from src.database.base import Base


class Tracking(Base):
    __tablename__ = "tracking_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)

    vehicle_id: Mapped[int] = mapped_column(
        ForeignKey("vehicles_table.id", ondelete="CASCADE"),
        index=True,
    )
    camera_id: Mapped[int] = mapped_column(
        ForeignKey("camera_table.id", ondelete="CASCADE"),
        index=True,
    )
    spot_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("spots_table.id", ondelete="SET NULL"),
        nullable=True,
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        default=datetime.utcnow,
    )

    event_type: Mapped[str] = mapped_column(String(50))  # enter, exit, pass, park

    # Координаты в кадре (если нужно)
    bbox: Mapped[dict] = mapped_column(JSON, nullable=True)

    # Связи
    vehicle: Mapped["Vehicles"] = relationship(
        "Vehicles",
        back_populates="tracking_history",
    )
    camera: Mapped["Cameras"] = relationship("Cameras")
    spot: Mapped[Optional["Spot"]] = relationship("Spot")

    # Индекс для быстрых запросов по времени
    __table_args__ = (
        Index("idx_tracking_time", "timestamp", "vehicle_id"),
    )
