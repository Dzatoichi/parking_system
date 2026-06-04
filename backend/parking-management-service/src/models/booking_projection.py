from datetime import datetime

from sqlalchemy import DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base
from src.models.status.booking_status import BookingStatus


class BookingProjection(Base):
    __tablename__ = "booking_projection"

    booking_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parking_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    vehicle_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    spot_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    spot_number: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name="bookingstatus"),
        nullable=False,
        index=True,
    )
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
