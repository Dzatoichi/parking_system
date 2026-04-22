from typing import Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from src.models.vehicles import Vehicles
from src.models.tracking import Tracking


class VehicleDAO:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session


    async def get_by_id(self, vehicle_id: int) -> Optional[Vehicles]:
        result = await self._session.execute(
            select(Vehicles).where(Vehicles.id == vehicle_id)
        )
        return result.scalar_one_or_none()

    async def get_by_plate(self, plate_number: str) -> Optional[Vehicles]:
        result = await self._session.execute(
            select(Vehicles).where(Vehicles.plate_number == plate_number)
        )
        return result.scalar_one_or_none()

    async def get_all(
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

        rows = await self._session.execute(
            query.order_by(Vehicles.id).offset(offset).limit(limit)
        )
        total = await self._session.execute(count_query)
        return list(rows.scalars().all()), total.scalar_one()


    async def create(self, vehicle: Vehicles) -> Vehicles:
        self._session.add(vehicle)
        await self._session.flush()
        await self._session.refresh(vehicle)
        return vehicle

    async def update_location(
        self,
        vehicle_id: int,
        camera_id: int,
        is_inside: bool,
    ) -> Optional[Vehicles]:
        result = await self._session.execute(
            update(Vehicles)
            .where(Vehicles.id == vehicle_id)
            .values(
                last_camera_id=camera_id,
                is_inside=is_inside,
                last_seen=datetime.utcnow(),
            )
            .returning(Vehicles)
        )
        return result.scalar_one_or_none()

    async def set_blocked(self, vehicle_id: int, blocked: bool) -> Optional[Vehicles]:
        result = await self._session.execute(
            update(Vehicles)
            .where(Vehicles.id == vehicle_id)
            .values(is_blocked=blocked)
            .returning(Vehicles)
        )
        return result.scalar_one_or_none()

    async def delete(self, vehicle_id: int) -> bool:
        vehicle = await self.get_by_id(vehicle_id)
        if vehicle is None:
            return False
        await self._session.delete(vehicle)
        await self._session.flush()
        return True


class TrackingDAO:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_event(self, event: Tracking) -> Tracking:
        self._session.add(event)
        await self._session.flush()
        await self._session.refresh(event)
        return event

    async def get_vehicle_history(
        self,
        vehicle_id: int,
        limit: int = 100,
    ) -> list[Tracking]:
        result = await self._session.execute(
            select(Tracking)
            .where(Tracking.vehicle_id == vehicle_id)
            .order_by(Tracking.timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_by_id(self, event_id: int) -> Optional[Tracking]:
        result = await self._session.execute(
            select(Tracking).where(Tracking.id == event_id)
        )
        return result.scalar_one_or_none()

    async def get_spot_history(
            self,
            spot_id: int,
            from_dt: datetime,
            to_dt: datetime,
            limit: int = 100,
    ) -> list[Tracking]:
        result = await self._session.execute(
            select(Tracking)
            .where(
                Tracking.spot_id == spot_id,
                Tracking.timestamp >= from_dt,
                Tracking.timestamp <= to_dt,
            )
            .order_by(Tracking.timestamp.desc())
            .limit(limit)
        )
        return list(result.scalars().all())