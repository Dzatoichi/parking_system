# Экспортируем всё из одного места.
# В роутере достаточно написать: from src.schemas import SpotRead, SpotStatusUpdate

from .base_schema import BaseSchema
from .common import PaginatedResponse, ErrorResponse, SuccessResponse

from .parking_schemas import ParkingCreate, ParkingUpdate, ParkingRead, ParkingStats
from .spot_schemas import (
    SpotCoordinates,
    SpotCreate,
    SpotStatusUpdate,
    SpotCoordinatesUpdate,
    SpotRead,
    SpotReadShort,
)
from .camera_schemas import CameraCreate, CameraUpdate, CameraRead, CameraNetworkRead
from .vehicle_schemas import (
    BoundingBox,
    VehicleCreate,
    VehicleRead,
    VehicleLocationUpdate,
    TrackingTaskCreate,
    TrackingTaskRead,
    TrackingEventRead,
    VehicleRouteRead,
    VehicleDurationRead,
)

__all__ = [
    "BaseSchema",
    "PaginatedResponse", "ErrorResponse", "SuccessResponse",
    "ParkingCreate", "ParkingUpdate", "ParkingRead", "ParkingStats",
    "SpotCoordinates", "SpotCreate", "SpotStatusUpdate", "SpotCoordinatesUpdate",
    "SpotRead", "SpotReadShort",
    "CameraCreate", "CameraUpdate", "CameraRead", "CameraNetworkRead",
    "BoundingBox", "VehicleCreate", "VehicleRead", "VehicleLocationUpdate",
    "TrackingTaskCreate", "TrackingTaskRead", "TrackingEventRead",
    "VehicleRouteRead", "VehicleDurationRead",
]