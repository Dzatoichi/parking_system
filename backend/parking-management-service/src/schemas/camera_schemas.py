from typing import Optional

from pydantic import Field, field_validator

from src.models.status.camera_status import CameraStatus

from .base_schema import BaseSchema


def validate_camera_source(value: str) -> str:
    if not (
        value.startswith("rtsp://")
        or value.startswith("rtsps://")
        or value.startswith("http://")
        or value.startswith("https://")
        or value.startswith("/app/")
    ):
        raise ValueError("camera source must be rtsp(s), http(s), or an /app/ video path")
    return value


class CameraCreate(BaseSchema):
    rtsp_url: str = Field(
        min_length=4,
        max_length=500,
        examples=["rtsp://admin:password@192.168.1.10:554/stream1", "/app/videos/test.ts"],
    )
    position_x: Optional[float] = Field(default=None)
    position_y: Optional[float] = Field(default=None)
    is_calibrated: bool = Field(default=False)
    monitored_spot_ids: list[int] = Field(default_factory=list)

    @field_validator("rtsp_url")
    @classmethod
    def validate_rtsp_url(cls, value: str) -> str:
        return validate_camera_source(value)


class CameraUpdate(BaseSchema):
    rtsp_url: Optional[str] = Field(default=None, min_length=4, max_length=500)
    status: Optional[CameraStatus] = None
    position_x: Optional[float] = None
    position_y: Optional[float] = None
    is_calibrated: Optional[bool] = None
    monitored_spot_ids: Optional[list[int]] = None

    @field_validator("rtsp_url")
    @classmethod
    def validate_rtsp_url(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return validate_camera_source(value)


class CameraRead(BaseSchema):
    id: int
    rtsp_url: str
    status: CameraStatus
    position_x: Optional[float]
    position_y: Optional[float]
    is_calibrated: bool
    parking_id: int
    monitored_spot_ids: list[int] = Field(default_factory=list)


class CameraNetworkRead(BaseSchema):
    parking_id: int
    cameras: list[CameraRead]
    total: int
