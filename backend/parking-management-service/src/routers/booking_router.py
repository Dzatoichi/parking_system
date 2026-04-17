from fastapi import APIRouter, status, Query, Depends
from datetime import datetime
from src.schemas.booking_schemas import (
    BookingCreate, BookingRead, BookingUpdate, BookingListResponse
)
from src.utils.dependencies import get_booking_service

booking_router = APIRouter(prefix="/bookings", tags=["bookings"])


@booking_router.post(
    "",
    response_model=BookingRead,
    status_code=status.HTTP_201_CREATED,
    summary="Создать бронирование"
)
async def create_booking(
        body: BookingCreate,
        service=Depends(get_booking_service)
) -> BookingRead:
    return await service.create_booking(body)


@booking_router.get(
    "/{user_id}",
    response_model=BookingListResponse,
    summary="Получить бронирования пользователя"
)
async def get_user_bookings(
        user_id: int,
        page: int = Query(1, ge=1),
        size: int = Query(20, ge=1, le=100),
        service=Depends(get_booking_service)
) -> BookingListResponse:
    return await service.get_user_bookings(user_id, page, size)


@booking_router.get(
    "/detail/{booking_id}",
    response_model=BookingRead,
    summary="Получить детали бронирования"
)
async def get_booking(
        booking_id: int,
        service=Depends(get_booking_service)
) -> BookingRead:
    return await service.get_booking(booking_id)


@booking_router.patch(
    "/{booking_id}",
    response_model=BookingRead,
    summary="Отменить/обновить бронирование"
)
async def update_booking(
        booking_id: int,
        body: BookingUpdate,
        service=Depends(get_booking_service)
) -> BookingRead:
    if body.status:
        if body.status.value == "cancelled":
            return await service.cancel_booking(booking_id, body.cancellation_reason)
        elif body.status.value == "confirmed":
            return await service.confirm_booking(booking_id)

    return await service.get_booking(booking_id)


@booking_router.get(
    "",
    summary="Получить доступные места для бронирования"
)
async def get_available_spots(
        parking_id: int,
        start_time: datetime = Query(...),
        end_time: datetime = Query(...),
        service=Depends(get_booking_service)
):
    return await service.get_available_spots(parking_id, start_time, end_time)