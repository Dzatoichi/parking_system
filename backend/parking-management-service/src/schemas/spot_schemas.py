from typing import Optional
from pydantic import Field, model_validator
from .base_schema import BaseSchema
from src.models.status.spot_status import SpotStatus
from src.models.type.spot_type import SpotType

class SpotCoordinates(BaseSchema):
    """
    Координаты полигона разметки одного места на схеме парковки.
    Хранится как JSON в БД (поле spot_coordinates).

    points — список точек полигона в пикселях схемы.
    center_x / center_y — геометрический центр (для поиска ближайшего места).
    """
    points: list[list[float]] = Field(
        min_length=4,
        description="4 точки [[x1,y1],[x2,y2],[x3,y3]]",
        examples=[[[10.0, 20.0], [50.0, 20.0], [50.0, 60.0], [10.0, 60.0]]],
    )
    center_x: float
    center_y: float

    @model_validator(mode="after")
    def check_points_are_pairs(self) -> "SpotCoordinates":
        for point in self.points:
            if len(point) != 2:
                raise ValueError("Каждая точка должна быть парой [x, y]")
        return self


class SpotCreate(BaseSchema):
    """
    Тело запроса при создании парковочного места.
    POST /parking/{parking_id}/spots
    """
    spot_number: str = Field(
        min_length=1,
        max_length=10,
        pattern=r"^[A-Za-z0-9\-]+$",
        examples=["A-01", "B12"],
    )
    spot_type: SpotType = SpotType.STANDARD
    spot_coordinates: SpotCoordinates
    # parking_id берётся из path-параметра, не из тела запроса


class SpotStatusUpdate(BaseSchema):
    """
    Смена статуса места.
    PATCH /spots/{spot_id}/status

    vehicle_id обязателен при установке OCCUPIED,
    должен быть None при FREE/RESERVED.
    """
    status: SpotStatus
    vehicle_id: Optional[int] = None
    source: str | None = None
    payload: dict | None = None

    @model_validator(mode="after")
    def vehicle_required_when_occupied(self) -> "SpotStatusUpdate":
        if self.status == SpotStatus.OCCUPIED and self.vehicle_id is None:
            raise ValueError("vehicle_id обязателен при статусе OCCUPIED")
        if self.status == SpotStatus.FREE and self.vehicle_id is not None:
            raise ValueError("vehicle_id должен быть None при статусе FREE")
        return self


class SpotOwnershipRegister(BaseSchema):
    parking_id: int | None = Field(default=None, gt=0)
    spot_number: str | None = Field(default=None, min_length=1, max_length=10)
    hourly_rate: float = Field(default=100, ge=0)
    penalty: float = Field(default=0, ge=0)
    rental_enabled: bool = False


class SpotRentalUpdate(BaseSchema):
    hourly_rate: float | None = Field(default=None, ge=0)
    penalty: float | None = Field(default=None, ge=0)
    rental_enabled: bool | None = None
    status: SpotStatus | None = None


class SpotCoordinatesUpdate(BaseSchema):
    """
    Обновление разметки места (после перемаркировки).
    PATCH /spots/{spot_id}/coordinates
    """
    spot_coordinates: SpotCoordinates


class SpotRead(BaseSchema):
    """
    Полный объект парковочного места — возвращается клиенту.
    """
    id: int
    spot_number: str
    spot_type: SpotType
    spot_status: SpotStatus
    spot_coordinates: SpotCoordinates
    parking_id: int
    current_vehicle_id: Optional[int] = None
    owner_id: Optional[int] = None
    rental_enabled: bool = False
    hourly_rate: float = 100
    penalty: float = 0


class SpotReadShort(BaseSchema):
    """
    Облегчённая версия — для списка всех мест парковки.
    GET /spots/{parking_id}
    Не включает coordinates, чтобы не раздувать ответ.
    """
    id: int
    spot_number: str
    spot_type: SpotType
    spot_status: SpotStatus
    current_vehicle_id: Optional[int] = None
    owner_id: Optional[int] = None
    rental_enabled: bool = False
    hourly_rate: float = 100
    penalty: float = 0
