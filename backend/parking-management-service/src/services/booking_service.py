from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.dao.booking_dao import BookingDAO
from src.dao.parking_dao import ParkingDAO
from src.dao.spot_dao import SpotDAO
from src.models.booking import Booking
from src.models.status.booking_status import BookingStatus
from src.models.status.spot_status import SpotStatus
from src.schemas.booking_schemas import (
    AvailableSpotInfo,
    BookingCreate,
    BookingListResponse,
    BookingRead,
    BookingUpdate,
)
from src.services.spot_service import SpotService


class BookingService:
    def __init__(self, booking_dao: BookingDAO, spot_service: SpotService, parking_dao: ParkingDAO) -> None:
        self._booking_dao = booking_dao
        self._spot_service = spot_service
        self._parking_dao = parking_dao

    async def create_booking(self, booking_create: BookingCreate) -> BookingRead:
        spot = await self._spot_service.get_spot_by_id(booking_create.spot_id)
        if spot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Место с id={booking_create.spot_id} не найдено",
            )

        if spot.spot_status == SpotStatus.OCCUPIED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Нельзя забронировать уже занятое место",
            )

        conflicts = await self._booking_dao.get_conflicting_bookings(
            booking_create.spot_id,
            booking_create.start_time,
            booking_create.end_time,
        )
        if conflicts:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Место уже забронировано на этот период",
            )

        booking_dict = {
            "user_id": booking_create.user_id,
            "spot_id": booking_create.spot_id,
            "start_time": booking_create.start_time,
            "end_time": booking_create.end_time,
            "status": BookingStatus.PENDING
        }
        created_booking = await self._booking_dao.create(booking_dict)
        upd_spot_status = await self._spot_service.change_status(spot.id, SpotStatus.RESERVED)
        await self._sync_parking_available_spots(spot.parking_id)

        return BookingRead.model_validate(booking_dict)

    async def get_booking(self, booking_id: int) -> BookingRead:
        booking = await self._get_booking_or_404(booking_id)
        return BookingRead.model_validate(booking)

    async def get_bookings(self, page: int = 1, size: int = 50) -> BookingListResponse:
        bookings, total = await self._booking_dao.get_all_paginated(page=page, size=size)

        items = [BookingRead.model_validate(booking) for booking in bookings]

        return BookingListResponse.create(
            items=items,
            total=total,
            page=page,
            size=size
        )


    async def get_user_bookings(
        self,
        user_id: int,
        page: int = 1,
        size: int = 20,
    ) -> BookingListResponse:
        offset = (page - 1) * size
        bookings, total = await self._booking_dao.get_user_bookings(
            user_id,
            offset=offset,
            limit=size,
        )
        return BookingListResponse.create(
            items=[BookingRead.model_validate(item) for item in bookings],
            total=total,
            page=page,
            size=size,
        )

    # async def get_all_spots(
    #         self,
    #         parking_id: int,
    # ) -> BookingListResponse:
    #     """
    #     Просмотр всех мест с фильтром
    #     """


    async def get_available_spots(
        self,
        parking_id: int,
        # start_time: datetime,
        # end_time: datetime,
    ) -> list[AvailableSpotInfo]:
        paginated_response = await self._spot_service.get_spots_by_parking(
            parking_id=parking_id,
        )

        spots = paginated_response.items
        total = paginated_response.total
        page = paginated_response.page
        size = paginated_response.size


        available_spots: list[AvailableSpotInfo] = []
        for spot in spots:
            if spot.spot_status == SpotStatus.OCCUPIED:
                continue

            # conflicts = await self._booking_dao.get_conflicting_bookings(
            #     spot.id,
            #     start_time,
            #     end_time,
            # )
            # if conflicts:
            #     continue

            available_spots.append(
                AvailableSpotInfo(
                    spot_id=spot.id,
                    parking_id=spot.parking_id,
                    spot_number=spot.spot_number,
                    spot_type=spot.spot_type,
                    current_status=spot.spot_status,
                    spot_coordinates=spot.spot_coordinates,
                    # available_from=start_time,
                    # available_until=end_time,
                )
            )

        return available_spots

    async def update_booking(
        self,
        booking_id: int,
        data: BookingUpdate,
    ) -> BookingRead:
        booking = await self._get_booking_or_404(booking_id)
        previous_status = booking.status

        if data.notes is not None:
            booking.notes = data.notes

        if data.status is not None:
            if data.status == BookingStatus.CONFIRMED:
                if booking.status != BookingStatus.PENDING:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Подтвердить можно только booking в статусе pending",
                    )
                booking.status = BookingStatus.CONFIRMED
            elif data.status in {
                BookingStatus.CANCELLED,
                BookingStatus.COMPLETED,
                BookingStatus.EXPIRED,
            }:
                if booking.status in {
                    BookingStatus.CANCELLED,
                    BookingStatus.COMPLETED,
                    BookingStatus.EXPIRED,
                }:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Бронирование уже завершено или отменено",
                    )
                booking.status = data.status
                if data.status == BookingStatus.CANCELLED:
                    booking.cancellation_reason = data.cancellation_reason
            elif data.status == BookingStatus.PENDING and booking.status != BookingStatus.PENDING:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Нельзя вернуть booking обратно в pending",
                )

        booking.updated_at = datetime.now(tz=timezone.utc)
        self._session.add(booking)

        if previous_status != booking.status:
            await self._sync_spot_status_after_booking_change(booking.spot_id)

        await self._session.commit()
        await self._session.refresh(booking)
        return BookingRead.model_validate(booking)

    async def _get_booking_or_404(self, booking_id: int) -> Booking:
        booking = await self._booking_dao.get_by_id(booking_id)
        if booking is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Бронирование с id={booking_id} не найдено",
            )
        return booking

    async def _sync_spot_status_after_booking_change(self, spot_id: int) -> None:
        spot = await self._spot_dao.get_by_id(spot_id)
        if spot is None or spot.spot_status == SpotStatus.OCCUPIED:
            return

        active_bookings = await self._booking_dao.get_active_for_spot(spot_id)
        new_status = SpotStatus.RESERVED if active_bookings else SpotStatus.FREE
        await self._spot_dao.update_status(spot_id, new_status, vehicle_id=spot.current_vehicle_id)
        await self._sync_parking_available_spots(spot.parking_id)

    async def _sync_parking_available_spots(self, parking_id: int) -> None:
        stats = await self._spot_dao.get_stats(parking_id)
        await self._parking_dao.update(parking_id, {"available_spots": stats["free"]})