from src.schemas.base_schema import BaseSchema


class SystemEventCreateSchema(BaseSchema):
    event_type: str
    entity_type: str
    entity_id: int
    parking_id: int
    message: str
    payload: dict