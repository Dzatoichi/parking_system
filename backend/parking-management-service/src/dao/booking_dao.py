from datetime import datetime, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.orm import selectinload


from src.dao.base_dao import BaseDAO
from src.models.booking import Booking
from src.models.status.booking_status import BookingStatus
from src.models.spots import Spot
from src.models.vehicles import Vehicles


class BookingDAO(BaseDAO[Booking]):
    def __init__(self) -> None:
        super().__init__(model=Booking)

    # async def get_by_id(self, booking_id: int) -> Booking | None:
    #     result = await self._session.execute(
    #         select(Booking).where(Booking.id == booking_id)
    #     )
    #     return result.scalar_one_or_none()

    @BaseDAO.with_exception
    async def get_by_id(self, booking_id: int) -> Booking | None:
        async with self._get_session() as session:
            result = await session.execute(
                select(self.model)
                .options(selectinload(self.model.spot), selectinload(self.model.vehicle))
                .where(self.model.id == booking_id)
            )
            return result.scalar_one_or_none()

    @BaseDAO.with_exception
    async def get_user_bookings(
        self,
        user_id: int,
        status_filter: BookingStatus | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> tuple[list[Booking], int]:
        async with self._get_session() as session:
            query = (
                select(self.model)
                .options(selectinload(self.model.spot), selectinload(self.model.vehicle))
                .where(self.model.user_id == user_id)
            )
            count_query = select(func.count(self.model.id)).where(self.model.user_id == user_id)
            if status_filter:
                query = query.where(self.model.status == status_filter)
                count_query = count_query.where(self.model.status == status_filter)
            res = await session.execute(query.order_by(self.model.start_time.desc()).offset(offset).limit(limit))
            total = await session.execute(count_query)
            return list(res.scalars().all()), total.scalar_one()

        # query = select(Booking).where(Booking.user_id == user_id)
        # count_query = select(func.count(Booking.id)).where(Booking.user_id == user_id)
        #
        # if status_filter is not None:
        #     query = query.where(Booking.status == status_filter)
        #     count_query = count_query.where(Booking.status == status_filter)
        #
        # rows = await self._session.execute(
        #     query.order_by(Booking.start_time.desc()).offset(offset).limit(limit)
        # )
        # total = await self._session.execute(count_query)
        # return list(rows.scalars().all()), total.scalar_one()

    @BaseDAO.with_exception
    async def get_conflicting_bookings(
        self,
        spot_id: int,
        start_time: datetime,
        end_time: datetime,
        exclude_booking_id: int | None = None,
    ) -> list[Booking]:
        async with self._get_session() as session:
            query = select(self.model).where(
                and_(
                    self.model.spot_id == spot_id,
                    self.model.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED]),
                    self.model.start_time < end_time,
                    self.model.end_time > start_time,
                )
            )
            if exclude_booking_id:
                query = query.where(self.model.id != exclude_booking_id)

            res = await session.execute(query)
            return list(res.scalars().all())

    @BaseDAO.with_exception
    async def get_active_for_spot(
        self,
        spot_id: int,
        now: datetime | None = None,
    ) -> list[Booking]:
        current_time = now or datetime.now(tz=timezone.utc)
        async with self._get_session() as session:
            stmt = select(self.model).where(
                    and_(
                        self.model.spot_id == spot_id,
                        self.model.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED]),
                        self.model.end_time > current_time,
                    )
                )
            res = await session.execute(stmt)
            return list(res.scalars().all())

    @BaseDAO.with_exception
    async def get_by_spot(
        self,
        spot_id: int,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[Booking], int]:
        async with self._get_session() as session:
            query = (
                select(self.model)
                .options(selectinload(self.model.spot), selectinload(self.model.vehicle))
                .where(self.model.spot_id == spot_id)
                .order_by(self.model.created_at.desc())
                .offset(offset)
                .limit(limit)
            )
            count_query = select(func.count(self.model.id)).where(self.model.spot_id == spot_id)
            rows = await session.execute(query)
            total = await session.execute(count_query)
            return list(rows.scalars().all()), total.scalar_one()

    @BaseDAO.with_exception
    async def get_all_with_spot(self) -> list[Booking]:
        async with self._get_session() as session:
            rows = await session.execute(
                select(self.model)
                .options(selectinload(self.model.spot), selectinload(self.model.vehicle))
                .order_by(self.model.created_at.desc())
            )
            return list(rows.scalars().all())

    @BaseDAO.with_exception
    async def get_paginated(
        self,
        page: int = 1,
        size: int = 50,
        *,
        parking_id: int | None = None,
        status_filter: BookingStatus | None = None,
        vehicle_plate: str | None = None,
        start_from: datetime | None = None,
        start_to: datetime | None = None,
        end_from: datetime | None = None,
        end_to: datetime | None = None,
    ) -> tuple[list[Booking], int]:
        offset = (page - 1) * size

        query = select(self.model).options(selectinload(self.model.spot), selectinload(self.model.vehicle))
        count_query = select(func.count(self.model.id))

        if parking_id is not None:
            query = query.join(Spot, Spot.id == self.model.spot_id).where(Spot.parking_id == parking_id)
            count_query = count_query.join(Spot, Spot.id == self.model.spot_id).where(Spot.parking_id == parking_id)

        if status_filter is not None:
            query = query.where(self.model.status == status_filter)
            count_query = count_query.where(self.model.status == status_filter)

        if vehicle_plate:
            plate_filter = f"%{vehicle_plate.strip().lower()}%"
            query = query.join(Vehicles, Vehicles.id == self.model.vehicle_id).where(
                func.lower(Vehicles.plate_number).like(plate_filter)
            )
            count_query = count_query.join(Vehicles, Vehicles.id == self.model.vehicle_id).where(
                func.lower(Vehicles.plate_number).like(plate_filter)
            )

        if start_from is not None:
            query = query.where(self.model.start_time >= start_from)
            count_query = count_query.where(self.model.start_time >= start_from)

        if start_to is not None:
            query = query.where(self.model.start_time <= start_to)
            count_query = count_query.where(self.model.start_time <= start_to)

        if end_from is not None:
            query = query.where(self.model.end_time >= end_from)
            count_query = count_query.where(self.model.end_time >= end_from)

        if end_to is not None:
            query = query.where(self.model.end_time <= end_to)
            count_query = count_query.where(self.model.end_time <= end_to)

        query = query.order_by(self.model.created_at.desc()).offset(offset).limit(size)

        async with self._get_session() as session:
            rows = await session.execute(query)
            total = await session.execute(count_query)
            return list(rows.scalars().all()), total.scalar_one()
