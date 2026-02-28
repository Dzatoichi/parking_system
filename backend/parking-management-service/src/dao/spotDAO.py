from typing import Optional
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func, and_

from src.models.spots.spot import Spot
from src.models.spots.status.spot_status import SpotStatus
from src.models.spots.type.spot_type import SpotType


class SpotsDAO:
    """
    Data Access Object — весь SQL для работы с парковочными местами.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session


    async def get_by_id(self, spot_id: int) -> Optional[Spot]:
        result = await self._session.execute(
            select(Spot).where(Spot.id == spot_id)
        )
        return result.scalar_one_or_none()

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
        rows = await self._session.execute(
            select(Spot)
            .where(where_clause)
            .order_by(Spot.spot_number)
            .offset(offset)
            .limit(limit)
        )

        # Запрос общего числа (для пагинации)
        total_result = await self._session.execute(
            select(func.count(Spot.id)).where(where_clause)
        )

        return list(rows.scalars().all()), total_result.scalar_one()

    async def get_by_number(self, parking_id: int, spot_number: str) -> Optional[Spot]:
        """Поиск места по номеру (A-01, B12...) внутри конкретной парковки."""
        result = await self._session.execute(
            select(Spot).where(
                and_(Spot.parking_id == parking_id, Spot.spot_number == spot_number)
            )
        )
        return result.scalar_one_or_none()

    async def get_by_vehicle(self, vehicle_id: int) -> Optional[Spot]:
        """Найти место, на котором сейчас стоит конкретное авто."""
        result = await self._session.execute(
            select(Spot).where(Spot.current_vehicle_id == vehicle_id)
        )
        return result.scalar_one_or_none()

    async def get_stats(self, parking_id: int) -> dict[str, int]:
        """
        Считает количество мест по каждому статусу одним запросом.
        Вместо денормализованного available_spots в Parking.
        """
        rows = await self._session.execute(
            select(Spot.spot_status, func.count(Spot.id))
            .where(Spot.parking_id == parking_id)
            .group_by(Spot.spot_status)
        )
        counts = {status.value: count for status, count in rows.all()}

        # Гарантируем все ключи в ответе
        return {
            "free": counts.get(SpotStatus.FREE.value, 0),
            "occupied": counts.get(SpotStatus.OCCUPIED.value, 0),
            "reserved": counts.get(SpotStatus.RESERVED.value, 0),
            "total": sum(counts.values()),
        }

    # WRITE (без commit — только flush в БД-сессию)
    async def create(self, spot: Spot) -> Spot:
        self._session.add(spot)
        await self._session.flush()  # получаем id, но не коммитим
        await self._session.refresh(spot)
        return spot

    async def create_bulk(self, spots: list[Spot]) -> list[Spot]:
        """Пакетное создание мест (при первичной разметке парковки)."""
        self._session.add_all(spots)
        await self._session.flush()
        for spot in spots:
            await self._session.refresh(spot)
        return spots

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

        result = await self._session.execute(
            update(Spot)
            .where(Spot.id == spot_id)
            .values(**values)
            .returning(Spot)
        )
        return result.scalar_one_or_none()

    async def update_coordinates(
        self,
        spot_id: int,
        coordinates: dict,
    ) -> Optional[Spot]:
        """Обновление разметки места (после перемаркировки)."""
        result = await self._session.execute(
            update(Spot)
            .where(Spot.id == spot_id)
            .values(spot_coordinates=coordinates)
            .returning(Spot)
        )
        return result.scalar_one_or_none()

    async def delete(self, spot_id: int) -> bool:
        spot = await self.get_by_id(spot_id)
        if spot is None:
            return False
        await self._session.delete(spot)
        await self._session.flush()
        return True