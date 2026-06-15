from typing import Optional, List
from datetime import datetime

from sqlalchemy import Boolean, Float, Integer, String, Enum, ForeignKey, UniqueConstraint, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base
from src.models.status.spot_status import SpotStatus
from src.models.type.spot_type import SpotType


class Spot(Base):
    __tablename__ = "spots_table"

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, index=True
    )
    spot_number: Mapped[str] = mapped_column(
        String(10), nullable=False
    )
    spot_type: Mapped[SpotType] = mapped_column(
        Enum(SpotType), nullable=False, default=SpotType.STANDARD
    )
    spot_status: Mapped[SpotStatus] = mapped_column(
        Enum(SpotStatus), nullable=False, default=SpotStatus.FREE, index=True
    )

    # Полигон разметки: {"points": [[x,y],...], "center_x": float, "center_y": float}
    spot_coordinates: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Время занятия места — нужно для расчёта длительности стоянки
    occupied_since: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # FK — nullable, SET NULL при удалении авто из системы
    current_vehicle_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("vehicles_table.id", ondelete="SET NULL"),
        nullable=True,
    )
    parking_id: Mapped[int] = mapped_column(
        ForeignKey("parkings_table.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    rental_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    hourly_rate: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    penalty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    # Связи
    parking: Mapped["ParkingBase"] = relationship(back_populates="spots")
    current_vehicle: Mapped[Optional["Vehicles"]] = relationship(
        "Vehicles",
        back_populates="current_spot",
        foreign_keys=[current_vehicle_id],
    )
    bookings: Mapped[List["Booking"]] = relationship(
        "Booking",
        back_populates="spot",
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("parking_id", "spot_number", name="uq_parking_spot"),
    )

    def __repr__(self) -> str:
        return f"<Spot #{self.spot_number} [{self.spot_status.value}]>"
