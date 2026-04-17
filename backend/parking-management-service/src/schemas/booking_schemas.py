from datetime import datetime
from pydantic import BaseModel, Field
from pydantic import field_validator
from enum import Enum

from pydantic_core.core_schema import ValidationInfo


class BookingStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    EXPIRED = "expired"


class BookingCreate(BaseModel):
    user_id: int = Field(..., gt=0, description="ID пользователя")
    spot_id: int = Field(..., gt=0, description="ID парковочного места")
    start_time: datetime = Field(..., description="Начало бронирования")
    end_time: datetime = Field(..., description="Конец бронирования")

    @field_validator("end_time")
    @classmethod
    def end_time_after_start(cls, v, info: ValidationInfo):
        start_time = info.data.get("start_time")
        if start_time and v <= start_time:
            raise ValueError("end_time должен быть позже start_time")
        return v


class BookingUpdate(BaseModel):
    status: BookingStatus = Field(None, description="Новый статус")
    notes: str = Field(None, max_length=500)
    cancellation_reason: str = Field(None, max_length=500, description="Причина отмены")


class BookingRead(BaseModel):
    id: int
    user_id: int
    spot_id: int
    start_time: datetime
    end_time: datetime
    status: BookingStatus
    created_at: datetime
    updated_at: datetime
    notes: str = None
    cancellation_reason: str = None

    class Config:
        from_attributes = True


class BookingListResponse(BaseModel):
    bookings: list[BookingRead]
    total: int
    page: int
    size: int
    pages: int


class AvailableSpotInfo(BaseModel):
    spot_id: int
    parking_id: int
    spot_number: int
    spot_type: str
    coordinates: dict = None
    available_from: datetime = None
    available_until: datetime = None


class BookingConflict(BaseModel):
    spot_id: int
    conflicts: list[BookingRead]