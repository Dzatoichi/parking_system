from typing import Optional
from datetime import datetime, timezone

from sqlalchemy import select, update, func, and_

from src.dao.base_dao import BaseDAO
from src.models.spots import Spot
from src.models.status.spot_status import SpotStatus
from src.models.type.spot_type import SpotType


class SpotDAO(BaseDAO[Spot]):
    """
    Класс, наследующий базовый класс BaseDAO, для работы
    с сущностями парковочных мест
    """

    def __init__(self):
        super().__init__(model=Spot)

    # @BaseDAO.with_exception
    # async def get_all(
    #         self,
    #         parking_id: int | None,
    #         spot_id: int | None,
    #         plate_number: int | None,
    #         status: SpotStatus | None,
    #         spot_type: SpotType | None,
    #         start_time: datetime | None,
    #         end_time: datetime | None,
    # ) -> list[Spot]:
    #     """
    #     Получение всех мест с фильтром по
    #     параметрам.
    #     """
    #     result = await self._session.execute(select(Spot).where(Spot.id == parking_id))

    # async def get_by_id(self, spot_id: int) -> Optional[Spot]:
    #     result = await self._session.execute(
    #         select(Spot).where(Spot.id == spot_id)
    #     )
    #     return result.scalar_one_or_none()

    @BaseDAO.with_exception
    async def get_by_parking(
        self,
        parking_id: int,
        status: Optional[SpotStatus] = None,
        spot_type: Optional[SpotType] = None,
        offset: int = 0,
        limit: int = 200,
    ) -> tuple[list[Spot], int]:
        """
        Возвращает (список мест, общее количество) с опциональной фильтрацией.
        Используется для пагинации.
        """
        conditions = [Spot.parking_id == parking_id]

        if status is not None:
            conditions.append(Spot.spot_status == status)
        if spot_type is not None:
            conditions.append(Spot.spot_type == spot_type)

        where_clause = and_(*conditions)

        # Запрос данных
        async with (self._get_session() as session):
            stmt = select(self.model).where(where_clause).order_by(self.model.spot_number).offset(offset).limit(limit)
            res = await session.execute(stmt)

            # Запрос общего числа (для пагинации)
            total_result = await session.execute(
                select(func.count(self.model.id)).where(where_clause)
            )
            return list(res.scalars().all()), total_result.scalar_one()


    @BaseDAO.with_exception
    async def get_by_number(self, parking_id: int, spot_number: str) -> Optional[Spot]:
        """Поиск места по номеру (A-01, B12...) внутри конкретной парковки."""
        async with (self._get_session() as session):
            stmt = select(self.model).where(and_(self.model.parking_id == parking_id), (self.model.spot_number == spot_number))
            res = await session.execute(stmt)
            return res.scalar_one_or_none()

    @BaseDAO.with_exception
    async def get_by_vehicle(self, vehicle_id: int) -> Optional[Spot]:
        """Найти место, на котором сейчас стоит конкретное авто."""
        async with (self._get_session() as session):
            stmt = select(self.model).where(self.model.current_vehicle_id == vehicle_id)
            res = await session.execute(stmt)
            return res.scalar_one_or_none()

    @BaseDAO.with_exception
    async def get_by_owner(self, owner_id: int) -> list[Spot]:
        async with self._get_session() as session:
            stmt = (
                select(self.model)
                .where(self.model.owner_id == owner_id)
                .order_by(self.model.parking_id, self.model.spot_number)
            )
            res = await session.execute(stmt)
            return list(res.scalars().all())

    @BaseDAO.with_exception
    async def update_rental_settings(
        self,
        spot_id: int,
        *,
        hourly_rate: float | None = None,
        penalty: float | None = None,
        rental_enabled: bool | None = None,
        owner_id: int | None = None,
        spot_status: SpotStatus | None = None,
    ) -> Optional[Spot]:
        values = {
            key: value
            for key, value in {
                "hourly_rate": hourly_rate,
                "penalty": penalty,
                "rental_enabled": rental_enabled,
                "owner_id": owner_id,
                "spot_status": spot_status,
            }.items()
            if value is not None
        }
        async with self._get_session() as session:
            stmt = update(self.model).where(self.model.id == spot_id).values(**values).returning(self.model)
            res = await session.execute(stmt)
            await session.commit()
            updated = res.scalar_one_or_none()
            if updated:
                await session.refresh(updated)
            return updated

    @BaseDAO.with_exception
    async def get_stats(self, parking_id: int) -> dict[str, int]:
        """
        Считает количество мест по каждому статусу одним запросом.
        Вместо денормализованного available_spots в Parking.
        """
        async with (self._get_session() as session):
            stmt = select(self.model.spot_status, func.count(self.model.id)
                          ).where(self.model.parking_id == parking_id).group_by(self.model.spot_status)
            res = await session.execute(stmt)
            counts = {status.value: count for status, count in res.all()}
            return {
                "free": counts.get(SpotStatus.FREE.value, 0),
                "occupied": counts.get(SpotStatus.OCCUPIED.value, 0),
                "reserved": counts.get(SpotStatus.RESERVED.value, 0),
                "total": sum(counts.values()),
            }

    # # WRITE (без commit — только flush в БД-сессию)
    # async def create(self, spot: Spot) -> Spot:
    #     self._session.add(spot)
    #     await self._session.flush()  # получаем id, но не коммитим
    #     await self._session.refresh(spot)
    #     return spot

    @BaseDAO.with_exception
    async def create_bulk(self, spots: list[Spot]) -> list[Spot]:
        """Пакетное создание мест (при первичной разметке парковки)."""
        async with (self._get_session() as session):
            await session.add_all(spots)
            await session.flush()
            for spot in spots:
                await session.refresh(spot)
            return spots

    @BaseDAO.with_exception
    async def update_status(
        self,
        spot_id: int,
        new_status: SpotStatus,
        vehicle_id: Optional[int] = None,
    ) -> Optional[Spot]:
        """
        Атомарное обновление статуса и привязанного авто.
        occupied_since выставляется при OCCUPIED и сбрасывается при FREE.
        """
        values: dict = {
            "spot_status": new_status,
            "current_vehicle_id": vehicle_id,
        }

        if new_status == SpotStatus.OCCUPIED:
            values["occupied_since"] = datetime.now(tz=timezone.utc)
        elif new_status == SpotStatus.FREE:
            values["occupied_since"] = None

        async with (self._get_session() as session):
            stmt = update(self.model).where(self.model.id == spot_id).values(**values).returning(self.model)
            res = await session.execute(stmt)
            updated = res.scalar_one_or_none()
            await session.commit()
            return updated

    @BaseDAO.with_exception
    async def update_coordinates(
        self,
        spot_id: int,
        coordinates: dict,
    ) -> Optional[Spot]:
        """Обновление разметки места (после перемаркировки)."""
        async with (self._get_session() as session):
            stmt = update(self.model).where(self.model.id == spot_id).values(spot_coordinates=coordinates).returning(self.model)
            res = await session.execute(stmt)
            return res.scalar_one_or_none()

    # async def delete(self, spot_id: int) -> bool:
    #     spot = await self.get_by_id(spot_id)
    #     if spot is None:
    #         return False
    #     await self._session.delete(spot)
    #     await self._session.flush()
    #     return True
