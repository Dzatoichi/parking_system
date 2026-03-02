from typing import Optional
from pydantic import Field, field_validator, AnyUrl
from .base_schema import BaseSchema
from src.models.status.camera_status import CameraStatus


class CameraCreate(BaseSchema):
    """
    Добавление камеры в сеть.
    POST /parking/{parking_id}/cameras
    """
    rtsp_url: str = Field(
        min_length=10,
        max_length=500,
        examples=["rtsp://admin:password@192.168.1.10:554/stream1"],
    )
    position_x: Optional[float] = Field(
        default=None,
        description="Позиция на схеме парковки (пиксели)",
    )
    position_y: Optional[float] = Field(
        default=None,
        description="Позиция на схеме парковки (пиксели)",
    )
    is_calibrated: bool = Field(
        default=False,
        description="True — камера привязана к конкретным spots и умеет менять их статус",
    )
    monitored_spot_ids: list[int] = Field(
        default_factory=list,
        description="ID мест, которые видит эта камера",
    )

    @field_validator("rtsp_url")
    @classmethod
    def validate_rtsp(cls, v: str) -> str:
        if not (v.startswith("rtsp://") or v.startswith("rtsps://")):
            raise ValueError("rtsp_url должен начинаться с rtsp:// или rtsps://")
        return v


class CameraUpdate(BaseSchema):
    """
    Частичное обновление камеры.
    PATCH /cameras/{camera_id}
    """
    rtsp_url: Optional[str] = Field(default=None, min_length=10, max_length=500)
    status: Optional[CameraStatus] = None
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    is_calibrated: Optional[bool] = None


class CameraRead(BaseSchema):
    """
    Полный объект камеры.
    """
    id: int
    rtsp_url: str
    status: CameraStatus
    position_x: Optional[float]
    position_y: Optional[float]
    is_calibrated: bool
    parking_id: int
    monitored_spot_ids: list[int] = Field(default_factory=list)


class CameraNetworkRead(BaseSchema):
    """
    Сеть камер парковки — список всех камер.
    GET /cameras/{parking_id}
    """
    parking_id: int
    cameras: list[CameraRead]
    total: int