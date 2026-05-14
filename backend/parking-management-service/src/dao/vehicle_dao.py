from typing import Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from src.dao.base_dao import BaseDAO
from src.models.vehicles import Vehicles
from src.models.tracking import Tracking


class VehicleDAO(BaseDAO[Vehicles]):
    def __init__(self) -> None:
        super().__init__(model=Vehicles)


    # async def get_by_id(self, vehicle_id: int) -> Optional[Vehicles]:
    #     result = await self._session.execute(
    #         select(Vehicles).where(Vehicles.id == vehicle_id)
    #     )
    #     return result.scalar_one_or_none()

    @BaseDAO.with_exception
    async def get_vehicle_me(
            self,
            user_id: int,
    ) -> list[Vehicles] | None:
        async with self._get_session() as session:
            stmt = select(self.model).where(self.model.owner_id == user_id)
            res = await session.execute(stmt)
            return list(res.scalars().all())

    @BaseDAO.with_exception
    async def get_by_plate(self, plate_number: str) -> Optional[Vehicles]:
        async with self._get_session() as session:
            stmt = select(self.model).where(self.model.plate_number == plate_number)
            res = await session.execute(stmt)
            return res.scalar_one_or_none()

    @BaseDAO.with_exception
    async def get_all_vehicles(
        self,
        only_inside: bool = False,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[Vehicles], int]:
        query = select(Vehicles)
        count_query = select(func.count(Vehicles.id))

        if only_inside:
            query = query.where(Vehicles.is_inside == True)
            count_query = count_query.where(Vehicles.is_inside == True)
        async with self._get_session() as session:
            stmt = query.order_by(self.model.id).offset(offset).limit(limit)
            rows = await session.execute(stmt)
            total = await session.execute(count_query)
            return list(rows.scalars().all()), total.scalar_one()


    # async def create(self, vehicle: Vehicles) -> Vehicles:
    #     self._session.add(vehicle)
    #     await self._session.flush()
    #     await self._session.refresh(vehicle)
    #     return vehicle

    @BaseDAO.with_exception
    async def update_location(
        self,
        vehicle_id: int,
        camera_id: int,
        is_inside: bool,
    ) -> Optional[Vehicles]:
        async with self._get_session() as session:
            stmt = update(self.model).where(self.model.id == vehicle_id).values(
                last_camera_id=camera_id,
                is_inside=is_inside,
                last_seen=datetime.now(),
            ).returning(self.model)
            res = await session.execute(stmt)
            return res.scalar_one_or_none()

    @BaseDAO.with_exception
    async def set_blocked(self, vehicle_id: int, blocked: bool) -> Optional[Vehicles]:
        async with self._get_session() as session:
            stmt = update(self.model).where(self.model.id == vehicle_id).values(is_blocked=blocked).returning(self.model)
            res = await session.execute(stmt)
            return res.scalar_one_or_none()

    # async def delete(self, vehicle_id: int) -> bool:
    #     vehicle = await self.get_by_id(vehicle_id)
    #     if vehicle is None:
    #         return False
    #     await self._session.delete(vehicle)
    #     await self._session.flush()
    #     return True


class TrackingDAO(BaseDAO[Tracking]):
    def __init__(self) -> None:
        super().__init__(Tracking)

    # @BaseDAO.with_exception
    # async def create_event(self, event: Tracking) -> Tracking:
    #     async with self._get_session() as session:
    #
    #         self._session.add(event)
    #         await self._session.flush()
    #         await self._session.refresh(event)
    #         return event

    @BaseDAO.with_exception
    async def get_vehicle_history(
        self,
        vehicle_id: int,
        limit: int = 100,
    ) -> list[Tracking]:
        async with self._get_session() as session:
            stmt = select(self.model).where(self.model.id == vehicle_id).order_by(self.model.timestamp.desc()).limit(limit)
            res = await session.execute(stmt)
            return list(res.scalars().all())

    # async def get_by_id(self, event_id: int) -> Optional[Tracking]:
    #     result = await self._session.execute(
    #         select(Tracking).where(Tracking.id == event_id)
    #     )
    #     return result.scalar_one_or_none()

    @BaseDAO.with_exception
    async def get_spot_history(
            self,
            spot_id: int,
            from_dt: datetime,
            to_dt: datetime,
            limit: int = 100,
    ) -> list[Tracking]:
        async with self._get_session() as session:
            stmt = select(self.model).where(
                self.model.id == spot_id,
                self.model.timestamp >= from_dt,
                self.model.timestamp <= to_dt,
            ).order_by(self.model.timestamp.desc()).limit(limit)
            res= await session.execute(stmt)
            return list(res.scalars().all())