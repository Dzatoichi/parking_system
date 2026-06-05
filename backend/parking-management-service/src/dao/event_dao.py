from typing import List

from sqlalchemy import select, func

from src.dao.base_dao import BaseDAO, T
from src.models.system_events import SystemEvent


class EventDAO(BaseDAO[SystemEvent]):
    """
    Data Access Object для работы с моделью событий,
    наследуется от BaseDAO поэтому пуст
    """
    def __init__(self) -> None:
        super().__init__(model=SystemEvent)

    async def get_all_paginated_by_parking(
            self,
            parking_id: int,
            page: int = 1,
            size: int = 50
    ) -> tuple[list[SystemEvent], int] | None:
        offset = (page - 1) * size

        stmt = (
            select(self.model)
            .where(self.model.parking_id == parking_id)
            .order_by(self.model.created_at.desc(), self.model.id.desc())
            .offset(offset)
            .limit(size)
        )
        count_stmt = select(func.count()).select_from(self.model).where(self.model.parking_id == parking_id)
        async with self._get_session() as session:
            total_result = await session.execute(count_stmt)
            total = total_result.scalar()

            result = await session.execute(stmt)
            items = result.scalars().all()

            return items, total
