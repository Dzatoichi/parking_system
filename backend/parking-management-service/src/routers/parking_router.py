from fastapi import APIRouter, Query, status

from src.schemas import ParkingCreate, ParkingUpdate, ParkingRead, PaginatedResponse
from src.utils.dependencies import ParkingServiceDep

parking_router = APIRouter(prefix="/parking", tags=["parking"])


@parking_router.get("", response_model=PaginatedResponse[ParkingRead])
async def get_parkings(
    service: ParkingServiceDep,
    only_active: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
) -> PaginatedResponse[ParkingRead]:
    return await service.get_all_parkings(only_active=only_active, page=page, size=size)


@parking_router.get("/{parking_id}", response_model=ParkingRead)
async def get_parking(
    parking_id: int,
    service: ParkingServiceDep,
) -> ParkingRead:
    return await service.get_parking(parking_id)


@parking_router.post("", response_model=ParkingRead, status_code=status.HTTP_201_CREATED)
async def create_parking(
    body: ParkingCreate,
    service: ParkingServiceDep,
) -> ParkingRead:
    return await service.create_parking(body)


@parking_router.patch("/{parking_id}", response_model=ParkingRead)
async def update_parking(
    parking_id: int,
    body: ParkingUpdate,
    service: ParkingServiceDep,
) -> ParkingRead:
    return await service.update_parking(parking_id, body)


@parking_router.delete("/{parking_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_parking(
    parking_id: int,
    service: ParkingServiceDep,
) -> None:
    await service.delete_parking(parking_id)