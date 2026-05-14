from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


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
