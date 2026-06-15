from datetime import datetime
from typing import Optional
from pydantic import Field, field_validator
from pydantic import ValidationInfo

from .base_schema import BaseSchema

class BoundingBox(BaseSchema):
    """
    Координаты детекции авто в кадре камеры (пиксели).
    Формат: xyxy (как в YOLO/ByteTrack).
    """
    x1: float = Field(ge=0)
    y1: float = Field(ge=0)
    x2: float = Field(ge=0)
    y2: float = Field(ge=0)
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    @field_validator("x2")
    @classmethod
    def x2_gt_x1(cls, v: float, info: ValidationInfo) -> float:
        x1 = info.data.get("x1")
        if x1 is not None and v <= x1:
            raise ValueError("x2 must be greater than x1")
        return v

    @field_validator("y2")
    @classmethod
    def y2_gt_y1(cls, v: float, info: ValidationInfo) -> float:
        y1 = info.data.get("y1")
        if "y1" in info.data and v <= y1:
            raise ValueError("y2 должно быть больше y1")
        return v

class VehicleCreate(BaseSchema):
    """
    Регистрация нового авто в системе.
    Обычно вызывается автоматически из CV-сервиса при первом въезде.
    POST /vehicles/
    """
    plate_number: str = Field(
        min_length=3,
        max_length=12,
        pattern=r"^[A-ZА-Я0-9\s\-]+$",
        description="Номерной знак в верхнем регистре",
        examples=["А123ВС77", "B456CD"],
    )
    brand: str | None = Field(default=None, max_length=80)
    color: str | None = Field(default=None, max_length=40)
    photo_urls: dict[str, str] | None = None

    @field_validator("plate_number")
    @classmethod
    def normalize_plate(cls, v: str) -> str:
        return v.strip().upper()

class MobileVehicleCreate(VehicleCreate):
    name: str | None = None
    brand_id: int | None = None
    body_type_id: int | None = None
    photos: dict[str, str] | None = None


class VehicleRead(BaseSchema):
    """
    Объект авто — возвращается клиенту.
    """
    id: int
    plate_number: str
    owner_id: int
    is_inside: bool
    is_blocked: bool
    last_seen: Optional[datetime]
    last_camera_id: Optional[int]
    brand: Optional[str] = None
    color: Optional[str] = None
    photo_urls: dict[str, str] | None = None


class VehicleBlockUpdate(BaseSchema):
    blocked: bool = Field(
        description="True — запретить въезд, False — снять запрет",
    )


class VehicleLocationUpdate(BaseSchema):
    """
    CV-сервис сообщает текущее местоположение авто.
    POST /vehicles/location

    Вызывается каждый раз, когда CV идентифицировал авто на кадре.
    features — вектор ReID (512-мерный) — нужен для обновления в pgvector.
    """
    plate_number: str = Field(min_length=3, max_length=12)
    camera_id: int
    bbox: BoundingBox
    timestamp: datetime
    event_type: str = Field(
        pattern=r"^(enter|exit|pass|park|leave_spot)$",
        description="enter — въезд, exit — выезд, pass — проехал мимо, park — встал, leave_spot — уехал с места",
        examples=["park"],
    )
    spot_id: Optional[int] = Field(
        default=None,
        description="Заполняется, если event_type=park или leave_spot",
    )
    features: list[float] | None = Field(
        default=None,
        min_length=512,
        max_length=512,
    )

# ───────────────────────────────────────────────
# TRACKING
# ───────────────────────────────────────────────

class TrackingTaskCreate(BaseSchema):
    """
    Задание на поиск авто на конкретной камере.
    POST /tracking/task

    Если plate_number не указан — трекать все авто на камере (режим мониторинга).
    Если указан — режим поиска конкретного авто (ReID-сравнение).
    """
    camera_id: int
    plate_number: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=12,
        description="Если None — мониторинг всех авто",
    )
    priority: int = Field(
        default=0,
        ge=0,
        le=10,
        description="Приоритет задачи. 10 — наивысший (розыск).",
    )


class TrackingTaskRead(BaseSchema):
    """
    Подтверждение принятого задания.
    """
    task_id: str = Field(description="UUID задания")
    camera_id: int
    plate_number: Optional[str]
    status: str = Field(description="queued | running | completed | failed")


class TrackingEventRead(BaseSchema):
    """
    Одно событие из истории трекинга авто.
    Используется в GET /tracking/{vehicle_id}/history
    """
    id: int
    camera_id: int
    # position_x/y камеры — для рисования маршрута на клиенте
    camera_position_x: Optional[float]
    camera_position_y: Optional[float]
    spot_id: Optional[int]
    event_type: str
    timestamp: datetime
    bbox: Optional[BoundingBox]


class VehicleRouteRead(BaseSchema):
    """
    Маршрут авто по парковке.
    GET /tracking/{vehicle_id}/history
    """
    vehicle_id: int
    plate_number: str
    events: list[TrackingEventRead]
    total_events: int


class VehicleDurationRead(BaseSchema):
    """
    Время нахождения авто на месте.
    GET /tracking/{vehicle_id}/duration
    """
    vehicle_id: int
    spot_id: int
    spot_number: str
    parked_at: datetime
    left_at: Optional[datetime] = Field(
        default=None,
        description="None — авто всё ещё на месте",
    )
    duration_minutes: Optional[float] = Field(
        default=None,
        description="None — авто всё ещё на месте",
    )


class VehicleFullInfo(BaseSchema):
    """
    Полная информация об автомобиле:
    - общие данные
    - текущий статус (на парковке / где, последняя камера/место)
    - последние события истории.
    """
    vehicle: VehicleRead
    history: VehicleRouteRead
