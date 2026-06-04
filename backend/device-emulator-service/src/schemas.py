from datetime import datetime
import enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class EventType(enum.Enum):
    SPOT_STATUS_CHANGED = "spot_status_changed"
    BOOKING_CREATES = "booking_created"
    BOOKING_CANCELED = "booking_canceled"
    BOOKING_COMPLETED = "booking_completed"
    BOOKING_CONFLICT = "booking_conflict"
    BARRIER_OPENED = "barrier_opened"
    BARRIER_CLOSED = "barrier_closed"
    LIGHTING_CHANGED = "lighting_changed"
    DEVICE_UNAVAILABLE = "device_unavailable"
    VEHICLE_DETECTED = "vehicle_detected"
    VEHICLE_DEPARTED = "vehicle_departed"


class SystemEventCreateSchema(BaseSchema):
    event_type: str
    entity_type: str
    entity_id: int
    parking_id: int
    message: str
    payload: dict


class LightingSetBody(BaseModel):
    on: bool = True
    brightness: int = Field(default=100, ge=0, le=100)
    simulate_unreachable: bool = False


class BarrierStateOut(BaseModel):
    position: str  # "open" | "closed"


class LightingStateOut(BaseModel):
    on: bool
    brightness: int


class ParkingDevicesStateOut(BaseModel):
    parking_id: int
    barrier: BarrierStateOut
    lighting: LightingStateOut


class CommandResultOut(BaseModel):
    success: bool
    parking_id: int
    device_kind: str
    action: str
    state: dict[str, Any]
    message: str | None = None


class IntegrationEventOut(BaseModel):
    id: int
    parking_id: int
    device_kind: str
    action: str
    success: bool
    error_message: str | None
    request_payload: dict[str, Any] | None
    response_payload: dict[str, Any] | None
    created_at: datetime


class IntegrationEventListOut(BaseModel):
    items: list[IntegrationEventOut]
    total: int
    page: int
    size: int
