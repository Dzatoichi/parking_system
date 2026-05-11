from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from src.dao.base_dao import BaseDAO
from src.models.parkings import ParkingBase


class ParkingDAO(BaseDAO[ParkingBase]):
    """
    Весь SQL для работы с парковками.
    Не делает commit — это ответственность сервиса.
    """

    def __init__(self) -> None:
        super().__init__(ParkingBase)

    # @BaseDAO.with_exception
    # async def get_by_id(self, parking_id: int) -> Optional[ParkingBase]:
    #     result = await self._session.execute(
    #         select(ParkingBase).where(ParkingBase.id == parking_id)
    #     )
    #     return result.scalar_one_or_none()

    @BaseDAO.with_exception
    async def get_all(
        self,
        only_active: bool = False,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[ParkingBase], int]:
        async with self._get_session() as session:

            query = select(self.model)
            count_query = select(func.count(self.model.id))

            if only_active:
                query = query.where(self.model.is_active == True)
                count_query = count_query.where(self.model.is_active == True)

            res = await session.execute(
                query.order_by(self.model.id).offset(offset).limit(limit)
            )
            total = await session.execute(count_query)
            return list(res.scalars().all()), total.scalar_one()

    @BaseDAO.with_exception
    async def get_by_name(self, name: str) -> Optional[ParkingBase]:
        async with self._get_session() as session:
            stmt = select(self.model).where(self.model.name == name)
            res = await session.execute(stmt)
            return res.scalar_one_or_none()

    # async def create(self, parking: ParkingBase) -> ParkingBase:
    #     self._session.add(parking)
    #     await self._session.flush()
    #     await self._session.refresh(parking)
    #     return parking

    # async def update(
    #     self,
    #     parking_id: int,
    #     values: dict,
    # ) -> Optional[ParkingBase]:
    #     result = await self._session.execute(
    #         update(ParkingBase)
    #         .where(ParkingBase.id == parking_id)
    #         .values(**values)
    #         .returning(ParkingBase)
    #     )
    #     return result.scalar_one_or_none()

    # async def delete(self, parking_id: int) -> bool:
    #     parking = await self.get_by_id(parking_id)
    #     if parking is None:
    #         return False
    #     await self._session.delete(parking)
    #     await self._session.flush()
    #     return True