from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Boolean, JSON

from src.database.base import Base

class ParkingBase(Base):
    __tablename__ = 'parkings_table'
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    address: Mapped[str] = mapped_column(String(200), nullable=False)
    total_spots: Mapped[int] = mapped_column(Integer, nullable=False)
    available_spots: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Геоданные (можно хранить как JSON)
    coordinates: Mapped[dict] = mapped_column(JSON, nullable=True)
    boundaries: Mapped[dict] = mapped_column(JSON, nullable=True)  # Полигон парковки

    # Настройки
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    settings: Mapped[dict] = mapped_column(JSON, default={})

    # Связи
    spots: Mapped[list["Spot"]] = relationship(
        back_populates="parking",
        cascade="all, delete-orphan"
    )
    cameras: Mapped[list["Cameras"]] = relationship(
        back_populates="parking",
        cascade="all, delete-orphan"
    )


