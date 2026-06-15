import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status

from src.models.status.spot_status import SpotStatus
from src.models.type.spot_type import SpotType
from src.schemas.spot_schemas import (
    SpotCreate,
    SpotOwnershipRegister,
    SpotRentalUpdate,
    SpotRead,
    SpotReadShort,
    SpotStatusUpdate,
    SpotCoordinatesUpdate,
)
from src.schemas.parking_schemas import ParkingStats
from src.schemas.common import PaginatedResponse
from src.models.status.booking_status import BookingStatus
from src.utils.dependencies import BookingServiceDep, SpotServiceDep, get_current_user_id

spot_router = APIRouter(prefix="/spots", tags=["spots"])


def _booking_amount(booking, hourly_rate: float) -> float:
    seconds = max(0.0, (booking.end_time - booking.start_time).total_seconds())
    return round((hourly_rate * seconds) / 3600, 2)


@spot_router.get(
    "/me",
    response_model=list[SpotRead],
    summary="Места в собственности текущего пользователя",
)
async def get_my_spots(
    service: SpotServiceDep,
    user_id: int = Depends(get_current_user_id),
) -> list[SpotRead]:
    return await service.get_owner_spots(user_id)


@spot_router.patch(
    "/{spot_id}/ownership",
    response_model=SpotRead,
    summary="Зарегистрировать место в собственность текущего пользователя",
)
async def register_spot_ownership(
    spot_id: int,
    body: SpotOwnershipRegister,
    service: SpotServiceDep,
    user_id: int = Depends(get_current_user_id),
) -> SpotRead:
    return await service.register_ownership(spot_id, user_id, body)


@spot_router.patch(
    "/{spot_id}/rental",
    response_model=SpotRead,
    summary="Обновить цену и доступность места для аренды",
)
async def update_spot_rental(
    spot_id: int,
    body: SpotRentalUpdate,
    service: SpotServiceDep,
    user_id: int = Depends(get_current_user_id),
) -> SpotRead:
    return await service.update_rental_settings(spot_id, user_id, body)


@spot_router.get(
    "/{spot_id}/rental-report",
    summary="Отчетность по месту в собственности",
)
async def get_spot_rental_report(
    spot_id: int,
    spot_service: SpotServiceDep,
    booking_service: BookingServiceDep,
    user_id: int = Depends(get_current_user_id),
) -> dict:
    spot = await spot_service.get_spot_by_id(spot_id)
    if spot.owner_id != user_id:
        from fastapi import HTTPException

        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Можно смотреть отчет только по своим местам")

    bookings = await booking_service.get_spot_bookings(spot_id=spot_id, page=1, size=100)
    paid_statuses = {BookingStatus.CONFIRMED, BookingStatus.COMPLETED}
    report_items = []
    transfer_count = 0
    transfer_amount = 0.0
    for booking in bookings.items:
        amount = _booking_amount(booking, spot.hourly_rate)
        paid = booking.status in paid_statuses
        if paid:
            transfer_count += 1
            transfer_amount += amount
        report_items.append(
            {
                "booking_id": booking.id,
                "user_id": booking.user_id,
                "user_name": booking.user_name,
                "vehicle_id": booking.vehicle_id,
                "vehicle_plate_number": booking.vehicle_plate_number,
                "status": booking.status.value,
                "start_time": booking.start_time.isoformat(),
                "end_time": booking.end_time.isoformat(),
                "created_at": booking.created_at.isoformat(),
                "updated_at": booking.updated_at.isoformat(),
                "hourly_rate": spot.hourly_rate,
                "amount": amount,
                "transfer_status": "succeeded" if paid else "pending",
            }
        )

    return {
        "spot": spot.model_dump(mode="json"),
        "bookings": report_items,
        "transfer_count": transfer_count,
        "transfer_amount": round(transfer_amount, 2),
        "currency": "RUB",
    }


@spot_router.get(
    "/{parking_id}/map",
    response_model=list[SpotRead],
    summary="Схема парковки с координатами",
)
async def get_spots_map(
    parking_id: int,
    service: SpotServiceDep,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
) -> list[SpotRead]:
    result = await service.get_spots_by_parking(
        parking_id=parking_id,
        page=page,
        size=size
    )
    return result.items


@spot_router.websocket("/{parking_id}/map/ws")
async def get_spots_map_ws(
    websocket: WebSocket,
    parking_id: int,
    service: SpotServiceDep,
) -> None:
    await websocket.accept()
    try:
        while True:
            result = await service.get_spots_by_parking(
                parking_id=parking_id,
                page=1,
                size=200,
            )
            await websocket.send_json({
                "type": "spots_map",
                "parking_id": parking_id,
                "data": [spot.model_dump(mode="json") for spot in result.items],
            })
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        return


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
    return await service.get_spot_by_id(spot_id)


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
