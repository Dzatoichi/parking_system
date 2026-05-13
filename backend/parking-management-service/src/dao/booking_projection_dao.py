from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from src.dao.base_dao import BaseDAO
from src.models.booking_projection import BookingProjection
from src.models.status.booking_status import BookingStatus


class BookingProjectionDAO(BaseDAO[BookingProjection]):
    def __init__(self) -> None:
        super().__init__(model=BookingProjection)

    @BaseDAO.with_exception
    async def upsert(self, payload: dict) -> BookingProjection:
        stmt = insert(self.model).values(**payload)
        stmt = stmt.on_conflict_do_update(
            index_elements=[self.model.booking_id],
            set_={
                "parking_id": payload["parking_id"],
                "user_id": payload["user_id"],
                "user_name": payload.get("user_name"),
                "spot_id": payload["spot_id"],
                "spot_number": payload["spot_number"],
                "status": payload["status"],
                "start_time": payload["start_time"],
                "end_time": payload["end_time"],
                "created_at": payload["created_at"],
                "updated_at": payload["updated_at"],
            },
        ).returning(self.model)

        async with self._get_session() as session:
            result = await session.execute(stmt)
            await session.commit()
            return result.scalar_one()

    @BaseDAO.with_exception
    async def replace_all(self, payloads: list[dict]) -> None:
        async with self._get_session() as session:
            await session.execute(delete(self.model))
            if payloads:
                await session.execute(insert(self.model), payloads)
            await session.commit()

    @BaseDAO.with_exception
    async def get_by_booking_id(self, booking_id: int) -> BookingProjection | None:
        async with self._get_session() as session:
            row = await session.execute(select(self.model).where(self.model.booking_id == booking_id))
            return row.scalar_one_or_none()

    @BaseDAO.with_exception
    async def get_paginated(
        self,
        *,
        page: int = 1,
        size: int = 50,
        parking_id: int | None = None,
        user_id: int | None = None,
        status_filter: BookingStatus | None = None,
        start_from: datetime | None = None,
        end_to: datetime | None = None,
    ) -> tuple[list[BookingProjection], int]:
        offset = (page - 1) * size

        query = select(self.model)
        count_query = select(func.count(self.model.booking_id))

        if parking_id is not None:
            query = query.where(self.model.parking_id == parking_id)
            count_query = count_query.where(self.model.parking_id == parking_id)

        if user_id is not None:
            query = query.where(self.model.user_id == user_id)
            count_query = count_query.where(self.model.user_id == user_id)

        if status_filter is not None:
            query = query.where(self.model.status == status_filter)
            count_query = count_query.where(self.model.status == status_filter)

        if start_from is not None:
            query = query.where(self.model.start_time >= start_from)
            count_query = count_query.where(self.model.start_time >= start_from)

        if end_to is not None:
            query = query.where(self.model.end_time <= end_to)
            count_query = count_query.where(self.model.end_time <= end_to)

        query = query.order_by(self.model.created_at.desc()).offset(offset).limit(size)

        async with self._get_session() as session:
            rows = await session.execute(query)
            total = await session.execute(count_query)
            return list(rows.scalars().all()), total.scalar_one()
