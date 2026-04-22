from pydantic import Field

from .base_schema import BaseSchema


class HourlyTrafficPoint(BaseSchema):
    hour: str = Field(description="Час в формате HH:00")
    vehicles: int = Field(ge=0)


class WeeklyOccupancyPoint(BaseSchema):
    day: str = Field(description="Короткое имя дня недели")
    occupancy: float = Field(ge=0.0, le=100.0)


class DurationBucket(BaseSchema):
    name: str
    value: float = Field(ge=0.0, le=100.0)
    color: str


class RecentEvent(BaseSchema):
    type: str
    plate: str
    time: str
    action: str


class MiniSpot(BaseSchema):
    id: int
    status: str
    plate: str | None = None


class AnalyticsOverview(BaseSchema):
    parking_id: int
    total_spots: int
    free_spots: int
    occupied_spots: int
    occupancy_rate: float = Field(ge=0.0, le=1.0)
    avg_duration_minutes: float
    peak_occupancy_percent: float = Field(ge=0.0, le=100.0)
    unique_visitors_week: int
    total_entries_today: int
    total_exits_today: int
    current_vehicles: int
    peak_hour: str
    hourly_traffic: list[HourlyTrafficPoint]
    weekly_occupancy: list[WeeklyOccupancyPoint]
    duration_distribution: list[DurationBucket]
    recent_events: list[RecentEvent]
    mini_spots: list[MiniSpot]
