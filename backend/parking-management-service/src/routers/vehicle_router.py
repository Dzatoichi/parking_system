from fastapi import APIRouter, Query, status

from src.schemas import (
    VehicleCreate,
    VehicleRead,
    VehicleLocationUpdate,
    VehicleRouteRead,
    PaginatedResponse,
)
from src.utils.dependencies import VehicleServiceDep

vehicle_router = APIRouter(prefix="/vehicles", tags=["vehicles"])


@vehicle_router.get("", response_model=PaginatedResponse[VehicleRead])
async def get_vehicles(
    service: VehicleServiceDep,
    only_inside: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
) -> PaginatedResponse[VehicleRead]:
    return await service.get_all_vehicles(only_inside=only_inside, page=page, size=size)


@vehicle_router.get("/{vehicle_id}", response_model=VehicleRead)
async def get_vehicle(
    vehicle_id: int,
    service: VehicleServiceDep,
) -> VehicleRead:
    return await service.get_vehicle(vehicle_id)


@vehicle_router.get("/by-plate/{plate_number}", response_model=VehicleRead)
async def get_vehicle_by_plate(
    plate_number: str,
    service: VehicleServiceDep,
) -> VehicleRead:
    return await service.get_vehicle_by_plate(plate_number)


@vehicle_router.post("", response_model=VehicleRead, status_code=status.HTTP_201_CREATED)
async def register_vehicle(
    body: VehicleCreate,
    service: VehicleServiceDep,
) -> VehicleRead:
    return await service.register_vehicle(body)


@vehicle_router.post("/location", response_model=VehicleRead)
async def update_location(
    body: VehicleLocationUpdate,
    service: VehicleServiceDep,
) -> VehicleRead:
    """Принимает событие от CV-сервиса."""
    return await service.process_location_event(body)


@vehicle_router.get("/{vehicle_id}/history", response_model=VehicleRouteRead)
async def get_vehicle_history(
    vehicle_id: int,
    service: VehicleServiceDep,
    limit: int = Query(default=100, ge=1, le=1000),
) -> VehicleRouteRead:
    return await service.get_vehicle_history(vehicle_id, limit=limit)


@vehicle_router.delete("/{vehicle_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vehicle(
    vehicle_id: int,
    service: VehicleServiceDep,
) -> None:
    await service.delete_vehicle(vehicle_id)