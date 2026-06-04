from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.database.base import Base


class EmulatedDevice(Base):
    """Состояние эмулируемого внешнего устройства (шлагбаум, освещение) по парковке."""

    __tablename__ = "emulated_devices"
    __table_args__ = (UniqueConstraint("parking_id", "device_kind", name="uq_emulated_device_parking_kind"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parking_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("parkings_table.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    state: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class IntegrationDeviceEvent(Base):
    """Журнал команд и ответов интеграции с внешними устройствами (FT-6.5)."""

    __tablename__ = "integration_device_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    parking_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    device_kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    request_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    response_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    success: Mapped[bool] = mapped_column(nullable=False, default=True)
    error_message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
