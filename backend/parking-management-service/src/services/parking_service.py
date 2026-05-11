from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from src.dao.parking_dao import ParkingDAO
from src.models.parkings import ParkingBase
from src.schemas import (
    ParkingCreate,
    ParkingUpdate,
    ParkingRead,
    PaginatedResponse,
)


class ParkingService:
    def __init__(self, parking_dao: ParkingDAO) -> None:
        self._dao = parking_dao


    async def get_parking(self, parking_id: int) -> ParkingRead:
        parking = await self._dao.get_by_id(parking_id)
        if parking is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Парковка с id={parking_id} не найдена",
            )
        return self._to_read(parking)

    async def get_all_parkings(
        self,
        only_active: bool = False,
        page: int = 1,
        size: int = 50,
    ) -> PaginatedResponse[ParkingRead]:
        offset = (page - 1) * size
        parkings, total = await self._dao.get_all(
            only_active=only_active, offset=offset, limit=size
        )
        items = [self._to_read(p) for p in parkings]
        return PaginatedResponse.create(items=items, total=total, page=page, size=size)


    async def create_parking(self, data: ParkingCreate) -> ParkingRead:
        existing = await self._dao.get_by_name(data.name)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Парковка с именем '{data.name}' уже существует",
            )

        parking = ParkingBase(
            name=data.name,
            address=data.address,
            total_spots=data.total_spots,
            available_spots=data.total_spots,  # изначально все свободны
            coordinates=data.coordinates,
            boundaries=data.boundaries,
            settings=data.settings,
        )
        parking = await self._dao.create(parking)
        await self._session.commit()
        return self._to_read(parking)

    async def update_parking(self, parking_id: int, data: ParkingUpdate) -> ParkingRead:
        existing = await self._dao.get_by_id(parking_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Парковка с id={parking_id} не найдена",
            )

        # Собираем только переданные поля
        values = data.model_dump(exclude_none=True)
        if not values:
            return self._to_read(existing)

        updated = await self._dao.update(parking_id, values)
        await self._session.commit()
        return self._to_read(updated)

    async def delete_parking(self, parking_id: int) -> None:
        parking = await self._dao.get_by_id(parking_id)
        if parking is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Парковка с id={parking_id} не найдена",
            )
        await self._dao.delete(parking_id)
        await self._session.commit()


    @staticmethod
    def _to_read(parking: ParkingBase) -> ParkingRead:
        return ParkingRead(
            id=parking.id,
            name=parking.name,
            address=parking.address,
            total_spots=parking.total_spots,
            available_spots=parking.available_spots,
            is_active=parking.is_active,
            coordinates=parking.coordinates,
            boundaries=parking.boundaries,
            settings=parking.settings or {},
        )