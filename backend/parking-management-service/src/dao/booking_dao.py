from datetime import datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.booking import Booking
from src.models.status.booking_status import BookingStatus


class BookingDAO:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, booking_id: int) -> Booking | None:
        result = await self._session.execute(
            select(Booking).where(Booking.id == booking_id)
        )
        return result.scalar_one_or_none()

    async def get_user_bookings(
        self,
        user_id: int,
        status_filter: BookingStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Booking], int]:
        query = select(Booking).where(Booking.user_id == user_id)
        count_query = select(func.count(Booking.id)).where(Booking.user_id == user_id)

        if status_filter is not None:
            query = query.where(Booking.status == status_filter)
            count_query = count_query.where(Booking.status == status_filter)

        rows = await self._session.execute(
            query.order_by(Booking.start_time.desc()).offset(offset).limit(limit)
        )
        total = await self._session.execute(count_query)
        return list(rows.scalars().all()), total.scalar_one()

    async def get_conflicting_bookings(
        self,
        spot_id: int,
        start_time: datetime,
        end_time: datetime,
        exclude_booking_id: int | None = None,
    ) -> list[Booking]:
        query = select(Booking).where(
            and_(
                Booking.spot_id == spot_id,
                Booking.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED]),
                Booking.start_time < end_time,
                Booking.end_time > start_time,
            )
        )

        if exclude_booking_id is not None:
            query = query.where(Booking.id != exclude_booking_id)

        result = await self._session.execute(query)
        return list(result.scalars().all())

    async def get_active_for_spot(
        self,
        spot_id: int,
        now: datetime | None = None,
    ) -> list[Booking]:
        current_time = now or datetime.now(tz=timezone.utc)
        result = await self._session.execute(
            select(Booking).where(
                and_(
                    Booking.spot_id == spot_id,
                    Booking.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED]),
                    Booking.end_time > current_time,
                )
            )
        )
        return list(result.scalars().all())
