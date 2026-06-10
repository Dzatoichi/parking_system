from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, ForeignKey, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database.base import Base
from src.models.status.booking_status import BookingStatus


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    vehicle_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("vehicles_table.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    spot_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("spots_table.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    end_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name="bookingstatus"),
        default=BookingStatus.PENDING,
        nullable=False,
        index=True,
    )
    notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    spot: Mapped["Spot"] = relationship(
        "Spot",
        back_populates="bookings",
        foreign_keys=[spot_id],
    )
    vehicle: Mapped[Optional["Vehicles"]] = relationship(
        "Vehicles",
        foreign_keys=[vehicle_id],
    )
