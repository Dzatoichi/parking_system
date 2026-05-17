from datetime import datetime

from src.schemas import BaseSchema


class SystemEventReadSchema(BaseSchema):
    id: int
    event_type: str
    entity_type: str
    entity_id: int
    parking_id: int
    message: str
    payload: dict
    created_at: datetime


class SystemEventCreateSchema(BaseSchema):
    event_type: str
    entity_type: str
    entity_id: int
    parking_id: int
    message: str
    payload: dict