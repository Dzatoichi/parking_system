from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from src.dao.booking_dao import BookingDAO
from src.dao.spot_dao import SpotDAO
from src.models.booking import Booking, BookingStatus
from src.models.status.spot_status import SpotStatus
from src.schemas.booking_schemas import (
    BookingCreate, BookingRead, BookingUpdate, BookingListResponse,
    AvailableSpotInfo
)


class BookingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.booking_dao = BookingDAO()
        self.spot_dao = SpotDAO(session)

    async def create_booking(
            self,
            booking_create: BookingCreate
    ) -> BookingRead:


        # 1. Проверить что место существует
        spot = await self.spot_dao.get_by_id(booking_create.spot_id)
        if not spot:
            raise ValueError(f"Место {booking_create.spot_id} не найдено")

        # 2. Проверить что место не забронировано
        conflicts = await self.booking_dao.get_spot_conflicting_bookings(
            self.session,
            booking_create.spot_id,
            booking_create.start_time,
            booking_create.end_time
        )
        if conflicts:
            raise ValueError(f"Место уже забронировано на этот период")

        # 3. Создать бронирование
        booking = Booking(
            user_id=booking_create.user_id,
            spot_id=booking_create.spot_id,
            start_time=booking_create.start_time,
            end_time=booking_create.end_time,
            status=BookingStatus.PENDING
        )

        self.session.add(booking)
        await self.session.commit()
        await self.session.refresh(booking)

        return BookingRead.from_orm(booking)

    async def get_booking(self, booking_id: int) -> BookingRead:
        booking = await self.booking_dao.get(self.session, booking_id)
        if not booking:
            raise ValueError(f"Бронирование {booking_id} не найдено")
        return BookingRead.from_orm(booking)

    async def get_user_bookings(
            self,
            user_id: int,
            page: int = 1,
            size: int = 20
    ) -> BookingListResponse:
        skip = (page - 1) * size
        bookings = await self.booking_dao.get_user_bookings(
            self.session,
            user_id,
            skip=skip,
            limit=size
        )

        # Получить всего для подсчета страниц
        all_bookings = await self.booking_dao.get_user_bookings(
            self.session,
            user_id,
            skip=0,
            limit=99999
        )

        total = len(all_bookings)
        pages = (total + size - 1) // size

        return BookingListResponse(
            bookings=[BookingRead.from_orm(b) for b in bookings],
            total=total,
            page=page,
            size=size,
            pages=pages
        )

    async def get_available_spots(
            self,
            parking_id: int,
            start_time: datetime,
            end_time: datetime
    ) -> List[AvailableSpotInfo]:

        # Получить все места парковки
        all_spots = await self.spot_dao.get_spots_by_parking(
            self.session,
            parking_id
        )

        available_spots = []

        for spot in all_spots:
            # Пропустить занятые места
            if spot.status == SpotStatus.OCCUPIED:
                continue

            # Проверить конфликты бронирований
            conflicts = await self.booking_dao.get_spot_conflicting_bookings(
                self.session,
                spot.id,
                start_time,
                end_time
            )

            if not conflicts:
                available_spots.append(
                    AvailableSpotInfo(
                        spot_id=spot.id,
                        parking_id=spot.parking_id,
                        spot_number=spot.spot_number,
                        spot_type=spot.spot_type.value if spot.spot_type else None,
                        coordinates=spot.coordinates
                    )
                )

        return available_spots

    async def cancel_booking(
            self,
            booking_id: int,
            reason: Optional[str] = None
    ) -> BookingRead:
        booking = await self.booking_dao.get(self.session, booking_id)
        if not booking:
            raise ValueError(f"Бронирование {booking_id} не найдено")

        if booking.status == BookingStatus.CANCELLED:
            raise ValueError("Бронирование уже отменено")

        booking.status = BookingStatus.CANCELLED
        booking.cancellation_reason = reason
        booking.updated_at = datetime.utcnow()

        self.session.add(booking)
        await self.session.commit()
        await self.session.refresh(booking)

        return BookingRead.from_orm(booking)

    async def confirm_booking(self, booking_id: int) -> BookingRead:
        booking = await self.booking_dao.get(self.session, booking_id)
        if not booking:
            raise ValueError(f"Бронирование {booking_id} не найдено")

        if booking.status != BookingStatus.PENDING:
            raise ValueError(f"Только PENDING бронирования могут быть подтверждены")

        booking.status = BookingStatus.CONFIRMED
        booking.updated_at = datetime.utcnow()

        self.session.add(booking)
        await self.session.commit()
        await self.session.refresh(booking)

        return BookingRead.from_orm(booking)