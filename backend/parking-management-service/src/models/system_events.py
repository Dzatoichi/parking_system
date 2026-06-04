from datetime import datetime

from sqlalchemy import Integer, String, ForeignKey, JSON, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models.type.event_type import EventType
from src.models.type.entity_type import EntityType

from src.database.base import Base

class SystemEvent(Base):
    __tablename__ = "events_table"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_type: Mapped[EventType] = mapped_column(String(15))
    entity_type: Mapped[EntityType] = mapped_column(String(15))
    entity_id: Mapped[int] = mapped_column(Integer, index=True) #TODO: организовать связь с таблицей сущности
    parking_id: Mapped[int] = mapped_column(Integer, ForeignKey("parkings_table.id"))
    message: Mapped[str] = mapped_column(String(30))
    payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


    
    