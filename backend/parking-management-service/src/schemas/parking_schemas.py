from typing import Optional
from pydantic import Field, field_validator
from .base_schema import BaseSchema


class ParkingCreate(BaseSchema):
    """
    Тело запроса при создании парковки.
    POST /parking/
    """
    name: str = Field(
        min_length=2,
        max_length=100,
        examples=["Парковка ТЦ Мега"],
    )
    address: str = Field(
        min_length=5,
        max_length=200,
        examples=["ул. Ленина, 1"],
    )
    total_spots: int = Field(
        gt=0,
        le=10_000,
        description="Общее количество мест. Должно быть > 0.",
    )
    # Необязательные поля
    coordinates: Optional[dict] = Field(
        default=None,
        description="Гео-центр парковки: {lat: float, lng: float}",
        examples=[{"lat": 55.751244, "lng": 37.618423}],
    )
    boundaries: Optional[dict] = Field(
        default=None,
        description="Полигон парковки: {points: [[x,y], ...]}",
    )
    settings: dict = Field(
        default_factory=dict,
        description="Произвольные настройки парковки",
    )


class ParkingUpdate(BaseSchema):
    """
    Тело запроса при частичном обновлении парковки.
    PATCH /parking/{parking_id}

    Все поля опциональны — передаём только то, что хотим изменить.
    """
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    address: Optional[str] = Field(default=None, min_length=5, max_length=200)
    is_active: Optional[bool] = None
    settings: Optional[dict] = None


class ParkingRead(BaseSchema):
    """
    Полный объект парковки — возвращается клиенту.
    available_spots вычисляется на уровне БД/сервиса, не хранится отдельно.
    """
    id: int
    name: str
    address: str
    total_spots: int
    available_spots: int  # считается через COUNT в сервисе
    is_active: bool
    coordinates: Optional[dict] = None
    boundaries: Optional[dict] = None
    settings: dict


class ParkingStats(BaseSchema):
    """
    Статистика парковки.
    GET /parking/{parking_id}/stats
    """
    parking_id: int
    total_spots: int
    free: int
    occupied: int
    reserved: int
    occupancy_rate: float = Field(
        description="Процент занятости, 0.0–1.0",
        ge=0.0,
        le=1.0,
    )
    avg_duration_minutes: Optional[float] = Field(
        default=None,
        description="Среднее время стоянки за последние 24 ч",
    )