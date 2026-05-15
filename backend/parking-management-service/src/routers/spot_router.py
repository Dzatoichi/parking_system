from typing import Optional

from fastapi import APIRouter, Query, status

from src.models.status.spot_status import SpotStatus
from src.models.type.spot_type import SpotType
from src.schemas.spot_schemas import (
    SpotCreate,
    SpotRead,
    SpotReadShort,
    SpotStatusUpdate,
    SpotCoordinatesUpdate,
)
from src.schemas.parking_schemas import ParkingStats
from src.schemas.common import PaginatedResponse
from src.utils.dependencies import SpotServiceDep

spot_router = APIRouter(prefix="/spots", tags=["spots"])


@spot_router.get(
    "/{parking_id}",
    response_model=PaginatedResponse[SpotReadShort],
    summary="Список мест парковки",
)
async def get_spots(
    parking_id: int,
    service: SpotServiceDep,
    status_filter: Optional[SpotStatus] = Query(default=None, alias="status"),
    type_filter: Optional[SpotType] = Query(default=None, alias="type"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
) -> PaginatedResponse[SpotReadShort]:
    return await service.get_spots_by_parking(
        parking_id=parking_id,
        filter_status=status_filter,
        filter_type=type_filter,
        page=page,
        size=size,
    )


@spot_router.get(
    "/{parking_id}/stats",
    response_model=ParkingStats,
    summary="Статистика мест парковки",
)
async def get_stats(
    parking_id: int,
    service: SpotServiceDep,
) -> ParkingStats:
    return await service.get_parking_stats(parking_id)


@spot_router.get(
    "/detail/{spot_id}",
    response_model=SpotRead,
    summary="Получить место по ID",
)
async def get_spot(
    spot_id: int,
    service: SpotServiceDep,
) -> SpotRead:
    return await service.get_spot(spot_id)


@spot_router.post(
    "/{parking_id}",
    response_model=SpotRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать парковочное место",
)
async def create_spot(
    parking_id: int,
    body: SpotCreate,
    service: SpotServiceDep,
) -> SpotRead:
    return await service.create_spot(parking_id, body)


@spot_router.post(
    "/{parking_id}/bulk",
    response_model=list[SpotRead],
    status_code=status.HTTP_201_CREATED,
    summary="Массовое создание мест",
)
async def create_spots_bulk(
    parking_id: int,
    body: list[SpotCreate],
    service: SpotServiceDep,
) -> list[SpotRead]:
    return await service.create_spots_bulk(parking_id, body)


@spot_router.patch(
    "/{spot_id}/status",
    response_model=SpotRead,
    summary="Сменить статус места",
)
async def change_status(
    spot_id: int,
    body: SpotStatusUpdate,
    service: SpotServiceDep,
) -> SpotRead:
    return await service.change_status(spot_id, body)


@spot_router.patch(
    "/{spot_id}/coordinates",
    response_model=SpotRead,
    summary="Обновить разметку места",
)
async def update_coordinates(
    spot_id: int,
    body: SpotCoordinatesUpdate,
    service: SpotServiceDep,
) -> SpotRead:
    return await service.update_coordinates(spot_id, body)


@spot_router.delete(
    "/{spot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Удалить место",
)
async def delete_spot(
    spot_id: int,
    service: SpotServiceDep,
) -> None:
    await service.delete_spot(spot_id)

# @spot_router.get(
#     path="/{parking_id}/map",
#     response_model=list[SpotRead],
#     summary="Получение возвращает список мест с координатами",
# )
# async def get_spot_map(
#         parking_id: int,
#         service: SpotServiceDep,
# ) -> list[SpotRead]:
#     return await service.get_spot_map(parking_id)