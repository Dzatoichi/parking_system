from datetime import datetime
from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.booking import Booking, BookingStatus
from src.dao.base_dao import BaseDAO


class BookingDAO(BaseDAO):
    model = Booking

    async def get_user_bookings(
            self,
            session: AsyncSession,
            user_id: int,
            status_filter: BookingStatus = None,
            skip: int = 0,
            limit: int = 50
    ) -> list[Booking]:
        query = select(self.model).where(
            self.model.user_id == user_id
        )

        if status_filter:
            query = query.where(self.model.status == status_filter)

        query = query.order_by(self.model.start_time.desc())
        query = query.offset(skip).limit(limit)

        result = await session.execute(query)
        return result.scalars().all()

    async def get_spot_conflicting_bookings(
            self,
            session: AsyncSession,
            spot_id: int,
            start_time: datetime,
            end_time: datetime,
            exclude_booking_id: int = None
    ) -> list[Booking]:

        query = select(self.model).where(
            and_(
                self.model.spot_id == spot_id,
                self.model.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED]),
                self.model.start_time < end_time,
                self.model.end_time > start_time
            )
        )

        if exclude_booking_id:
            query = query.where(self.model.id != exclude_booking_id)

        result = await session.execute(query)
        return result.scalars().all()

    async def get_parking_bookings_in_period(
            self,
            session: AsyncSession,
            parking_id: int,
            start_time: datetime,
            end_time: datetime,
            status_filter: BookingStatus = None
    ) -> list[Booking]:
        from src.models.spots import Spot

        query = select(self.model).join(
            Spot
        ).where(
            and_(
                Spot.parking_id == parking_id,
                self.model.start_time < end_time,
                self.model.end_time > start_time
            )
        )

        if status_filter:
            query = query.where(self.model.status == status_filter)

        result = await session.execute(query)
        return result.scalars().all()

    async def get_user_active_bookings(
            self,
            session: AsyncSession,
            user_id: int
    ) -> list[Booking]:
        now = datetime.utcnow()
        query = select(self.model).where(
            and_(
                self.model.user_id == user_id,
                self.model.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED]),
                self.model.start_time <= now,
                self.model.end_time > now
            )
        )
        result = await session.execute(query)
        return result.scalars().all()