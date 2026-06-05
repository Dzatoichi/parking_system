from datetime import datetime, timezone

from fastapi import HTTPException, status

from src.brokers.rabbitmq import BookingEventBroker
from src.dao.booking_dao import BookingDAO
from src.dao.booking_projection_dao import BookingProjectionDAO
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


class BookingService:
    def __init__(
        self,
        booking_dao: BookingDAO,
        spot_dao: SpotDAO,
        parking_dao: ParkingDAO,
        projection_dao: BookingProjectionDAO,
        event_broker: BookingEventBroker,
    ) -> None:
        self._booking_dao = booking_dao
        self._spot_dao = spot_dao
        self._parking_dao = parking_dao
        self._projection_dao = projection_dao
        self._event_broker = event_broker

    async def create_booking(self, booking_create: BookingCreate) -> BookingRead:
        spot = await self._spot_dao.get_by_id(booking_create.spot_id)
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

        created_booking = await self._booking_dao.create(
            {
                "user_id": booking_create.user_id,
                "vehicle_id": booking_create.vehicle_id,
                "spot_id": booking_create.spot_id,
                "start_time": booking_create.start_time,
                "end_time": booking_create.end_time,
                "status": BookingStatus.PENDING,
            }
        )
        await self._spot_dao.update_status(spot.id, SpotStatus.RESERVED, vehicle_id=spot.current_vehicle_id)
        await self._sync_parking_available_spots(spot.parking_id)
        await self._publish_projection_event(created_booking, spot.parking_id, spot.spot_number)
        return await self.get_booking(created_booking.id)

    async def get_booking(self, booking_id: int) -> BookingRead:
        booking = await self._get_booking_or_404(booking_id)
        projected = await self._projection_dao.get_by_booking_id(booking.id)
        if projected is not None:
            return self._projection_to_read(projected)
        return BookingRead.model_validate(booking)

    async def get_bookings(
        self,
        *,
        page: int = 1,
        size: int = 50,
        parking_id: int | None = None,
        status_filter: BookingStatus | None = None,
        start_from: datetime | None = None,
        end_to: datetime | None = None,
    ) -> BookingListResponse:
        bookings, total = await self._projection_dao.get_paginated(
            page=page,
            size=size,
            parking_id=parking_id,
            status_filter=status_filter,
            start_from=start_from,
            end_to=end_to,
        )
        return BookingListResponse.create(
            items=[self._projection_to_read(item) for item in bookings],
            total=total,
            page=page,
            size=size,
        )

    async def get_user_bookings(
        self,
        user_id: int,
        page: int = 1,
        size: int = 20,
    ) -> BookingListResponse:
        bookings, total = await self._projection_dao.get_paginated(page=page, size=size, user_id=user_id)
        return BookingListResponse.create(
            items=[self._projection_to_read(item) for item in bookings],
            total=total,
            page=page,
            size=size,
        )

    async def get_available_spots(
        self,
        parking_id: int,
    ) -> list[AvailableSpotInfo]:
        spots, _ = await self._spot_dao.get_by_parking(parking_id=parking_id, offset=0, limit=500)

        available_spots: list[AvailableSpotInfo] = []
        for spot in spots:
            if spot.spot_status == SpotStatus.OCCUPIED:
                continue

            available_spots.append(
                AvailableSpotInfo(
                    spot_id=spot.id,
                    parking_id=spot.parking_id,
                    spot_number=spot.spot_number,
                    spot_type=spot.spot_type,
                    current_status=spot.spot_status,
                    spot_coordinates=spot.spot_coordinates,
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

        updates: dict = {}
        if data.notes is not None:
            updates["notes"] = data.notes

        if data.status is not None:
            if data.status == BookingStatus.CONFIRMED and booking.status != BookingStatus.PENDING:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Подтвердить можно только booking в статусе pending",
                )
            if data.status in {BookingStatus.CANCELLED, BookingStatus.COMPLETED, BookingStatus.EXPIRED} and booking.status in {
                BookingStatus.CANCELLED,
                BookingStatus.COMPLETED,
                BookingStatus.EXPIRED,
            }:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Бронирование уже завершено или отменено",
                )
            if data.status == BookingStatus.PENDING and booking.status != BookingStatus.PENDING:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Нельзя вернуть booking обратно в pending",
                )

            updates["status"] = data.status
            if data.status == BookingStatus.CANCELLED:
                updates["cancellation_reason"] = data.cancellation_reason

        updates["updated_at"] = datetime.now(tz=timezone.utc)
        updated = await self._booking_dao.update(booking_id, **updates)
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Бронирование с id={booking_id} не найдено",
            )

        if previous_status != updated.status:
            await self._sync_spot_status_after_booking_change(updated.spot_id)

        spot = await self._spot_dao.get_by_id(updated.spot_id)
        assert spot is not None
        await self._publish_projection_event(updated, spot.parking_id, spot.spot_number)
        return await self.get_booking(updated.id)

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
        await self._parking_dao.update(parking_id, available_spots= stats["free"])

    async def _publish_projection_event(self, booking: Booking, parking_id: int, spot_number: str) -> None:
        await self._event_broker.publish(
            routing_key="booking.changed",
            payload={
                "booking_id": booking.id,
                "parking_id": parking_id,
                "user_id": booking.user_id,
                "vehicle_id": booking.vehicle_id,
                "spot_id": booking.spot_id,
                "spot_number": spot_number,
                "status": booking.status.value,
                "start_time": booking.start_time.isoformat(),
                "end_time": booking.end_time.isoformat(),
                "created_at": booking.created_at.isoformat(),
                "updated_at": booking.updated_at.isoformat(),
            },
        )

    @staticmethod
    def _projection_to_read(projection) -> BookingRead:
        return BookingRead(
            id=projection.booking_id,
            user_id=projection.user_id,
            user_name=projection.user_name,
            vehicle_id=getattr(projection, "vehicle_id", None),
            spot_id=projection.spot_id,
            spot_number=projection.spot_number,
            start_time=projection.start_time,
            end_time=projection.end_time,
            status=projection.status,
            created_at=projection.created_at,
            updated_at=projection.updated_at,
        )
