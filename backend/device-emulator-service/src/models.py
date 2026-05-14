from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, Integer, JSON, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


class EmulatedDevice(Base):
    __tablename__ = "emulated_devices"
    __table_args__ = (UniqueConstraint("parking_id", "device_kind", name="uq_emulated_device_parking_kind"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parking_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    device_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, insert_default=lambda: {})
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)


class IntegrationDeviceEvent(Base):
    __tablename__ = "integration_device_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parking_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    device_kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    request_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    response_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    success: Mapped[bool] = mapped_column(nullable=False, default=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
