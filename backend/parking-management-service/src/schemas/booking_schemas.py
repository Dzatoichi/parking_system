from datetime import datetime

from pydantic import Field, field_validator
from pydantic_core.core_schema import ValidationInfo

from src.models.status.booking_status import BookingStatus
from src.models.status.spot_status import SpotStatus
from src.models.type.spot_type import SpotType
from src.schemas.base_schema import BaseSchema
from src.schemas.common import PaginatedResponse
from src.schemas.spot_schemas import SpotCoordinates


class BookingCreate(BaseSchema):
    user_id: int = Field(..., gt=0, description="ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ")
    spot_id: int = Field(..., gt=0, description="ID РїР°СЂРєРѕРІРѕС‡РЅРѕРіРѕ РјРµСЃС‚Р°")
    start_time: datetime = Field(..., description="РќР°С‡Р°Р»Рѕ Р±СЂРѕРЅРёСЂРѕРІР°РЅРёСЏ")
    end_time: datetime = Field(..., description="РљРѕРЅРµС† Р±СЂРѕРЅРёСЂРѕРІР°РЅРёСЏ")

    @field_validator("end_time")
    @classmethod
    def end_time_after_start(cls, value: datetime, info: ValidationInfo) -> datetime:
        start_time = info.data.get("start_time")
        if start_time and value <= start_time:
            raise ValueError("end_time РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ РїРѕР·Р¶Рµ start_time")
        return value


class BookingUpdate(BaseSchema):
    status: BookingStatus | None = Field(default=None, description="РќРѕРІС‹Р№ СЃС‚Р°С‚СѓСЃ")
    notes: str | None = Field(default=None, max_length=500)
    cancellation_reason: str | None = Field(
        default=None,
        max_length=500,
        description="РџСЂРёС‡РёРЅР° РѕС‚РјРµРЅС‹",
    )


class BookingRead(BaseSchema):
    id: int
    user_id: int
    spot_id: int
    start_time: datetime
    end_time: datetime
    status: BookingStatus
    created_at: datetime
    updated_at: datetime
    notes: str | None = None
    cancellation_reason: str | None = None


class BookingListResponse(PaginatedResponse[BookingRead]):
    pass


class AvailableSpotInfo(BaseSchema):
    spot_id: int
    parking_id: int
    spot_number: str
    spot_type: SpotType
    current_status: SpotStatus
    spot_coordinates: SpotCoordinates
    available_from: datetime | None = None
    available_until: datetime | None = None


class BookingConflict(BaseSchema):
    spot_id: int
    conflicts: list[BookingRead]
