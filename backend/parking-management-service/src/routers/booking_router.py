from datetime import datetime

from fastapi import APIRouter, Query, status

from src.schemas.booking_schemas import (
    AvailableSpotInfo,
    BookingCreate,
    BookingListResponse,
    BookingRead,
    BookingUpdate,
)
from src.models.status.booking_status import BookingStatus
from src.utils.dependencies import BookingServiceDep

booking_router = APIRouter(prefix="/bookings", tags=["bookings"])

@booking_router.get(
    "/get_available",
    response_model=list[AvailableSpotInfo],
    summary="Получить доступные места для бронирования",
)
async def get_available_spots(
    parking_id: int,
    service: BookingServiceDep,
    # start_time: datetime = Query(...),
    # end_time: datetime = Query(...),
) -> list[AvailableSpotInfo]:
    return await service.get_available_spots(parking_id,)


@booking_router.get(
    "/me",
    response_model=BookingListResponse,
    summary="Активные бронирования текущего пользователя",
)
async def get_my_bookings(
    service: BookingServiceDep,
    user_id: int = Query(..., description="ID пользователя"),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> BookingListResponse:
    return await service.get_user_bookings(user_id, page, size)


@booking_router.post(
    "",
    response_model=BookingRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать бронирование",
)
async def create_booking(
    body: BookingCreate,
    service: BookingServiceDep,
) -> BookingRead:
    return await service.create_booking(body)

@booking_router.get(
    "",
    response_model=BookingListResponse,
    status_code=status.HTTP_200_OK,
    summary="Просмотр всех мест с фильтром",
)
async def get_bookings(
        booking_service: BookingServiceDep,
        parking_id: int | None = Query(default=None),
        status: BookingStatus | None = Query(default=None),
        from_: datetime | None = Query(default=None, alias="from"),
        to: datetime | None = Query(default=None),
        page: int = Query(default=1, ge=1),
        size: int = Query(default=50, ge=1, le=200),
) -> BookingListResponse:
    """
    Просмотр всех мест с филтрацией.
    """
    return await booking_service.get_bookings(
        page=page,
        size=size,
        parking_id=parking_id,
        status_filter=status,
        start_from=from_,
        end_to=to,
    )


@booking_router.get(
    "/detail/{booking_id}",
    response_model=BookingRead,
    summary="Получить детали бронирования по его id",
)
async def get_booking(
    booking_id: int,
    service: BookingServiceDep,
) -> BookingRead:
    return await service.get_booking(booking_id)


@booking_router.get(
    "/user/{user_id}",
    response_model=BookingListResponse,
    summary="Получить бронирования пользователя по его id",
)
async def get_user_bookings(
    user_id: int,
    service: BookingServiceDep,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
) -> BookingListResponse:
    return await service.get_user_bookings(user_id, page, size)

@booking_router.get(
    path="/{booking_id}",
    response_model=BookingRead,
    summary="Получить бронирование по id",
)
async def get_booking(
        booking_id: int,
        service: BookingServiceDep,
) -> BookingRead:
    return await service.get_booking(booking_id)


@booking_router.patch(
    "/{booking_id}",
    response_model=BookingRead,
    summary="Обновить статус или метаданные бронирования",
)
async def update_booking(
    booking_id: int,
    body: BookingUpdate,
    service: BookingServiceDep,
) -> BookingRead:
    return await service.update_booking(booking_id, body)



