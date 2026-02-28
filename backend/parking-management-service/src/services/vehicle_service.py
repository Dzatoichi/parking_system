from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from src.dao.vehicle_dao import VehicleDAO, TrackingDAO
from src.models.vehicles import Vehicles
from src.models.tracking import Tracking
from src.schemas import (
    VehicleCreate,
    VehicleRead,
    VehicleLocationUpdate,
    VehicleRouteRead,
    TrackingEventRead,
    PaginatedResponse,
)


class VehicleService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._dao = VehicleDAO(session)
        self._tracking_dao = TrackingDAO(session)


    async def get_vehicle(self, vehicle_id: int) -> VehicleRead:
        vehicle = await self._dao.get_by_id(vehicle_id)
        if vehicle is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Автомобиль с id={vehicle_id} не найден",
            )
        return self._to_read(vehicle)

    async def get_vehicle_by_plate(self, plate_number: str) -> VehicleRead:
        vehicle = await self._dao.get_by_plate(plate_number.upper())
        if vehicle is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Автомобиль с номером '{plate_number}' не найден",
            )
        return self._to_read(vehicle)

    async def get_all_vehicles(
        self,
        only_inside: bool = False,
        page: int = 1,
        size: int = 50,
    ) -> PaginatedResponse[VehicleRead]:
        offset = (page - 1) * size
        vehicles, total = await self._dao.get_all(
            only_inside=only_inside, offset=offset, limit=size
        )
        items = [self._to_read(v) for v in vehicles]
        return PaginatedResponse.create(items=items, total=total, page=page, size=size)


    async def register_vehicle(self, data: VehicleCreate) -> VehicleRead:
        existing = await self._dao.get_by_plate(data.plate_number)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Автомобиль '{data.plate_number}' уже зарегистрирован",
            )

        vehicle = Vehicles(
            plate_number=data.plate_number,
            is_inside=False,
        )
        vehicle = await self._dao.create(vehicle)
        await self._session.commit()
        return self._to_read(vehicle)

    async def process_location_event(self, data: VehicleLocationUpdate) -> VehicleRead:
        """
        Обрабатывает событие от CV-сервиса: регистрирует авто если новое,
        обновляет местоположение и создаёт запись в tracking.
        """
        vehicle = await self._dao.get_by_plate(data.plate_number)

        # Авто видим впервые — регистрируем автоматически
        if vehicle is None:
            vehicle = Vehicles(
                plate_number=data.plate_number,
                is_inside=data.event_type == "enter",
            )
            vehicle = await self._dao.create(vehicle)
        else:
            is_inside = vehicle.is_inside
            if data.event_type == "enter":
                is_inside = True
            elif data.event_type == "exit":
                is_inside = False

            vehicle = await self._dao.update_location(
                vehicle_id=vehicle.id,
                camera_id=data.camera_id,
                is_inside=is_inside,
            )

        # Создаём событие трекинга
        event = Tracking(
            vehicle_id=vehicle.id,
            camera_id=data.camera_id,
            spot_id=data.spot_id,
            timestamp=data.timestamp or datetime.now(tz=timezone.utc),
            event_type=data.event_type,
            bbox=data.bbox.model_dump() if data.bbox else None,
        )
        await self._tracking_dao.create_event(event)
        await self._session.commit()

        return self._to_read(vehicle)

    async def delete_vehicle(self, vehicle_id: int) -> None:
        vehicle = await self._dao.get_by_id(vehicle_id)
        if vehicle is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Автомобиль с id={vehicle_id} не найден",
            )
        if vehicle.is_inside:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Нельзя удалить автомобиль, который находится на парковке",
            )
        await self._dao.delete(vehicle_id)
        await self._session.commit()


    async def get_vehicle_history(
        self,
        vehicle_id: int,
        limit: int = 100,
    ) -> VehicleRouteRead:
        vehicle = await self._dao.get_by_id(vehicle_id)
        if vehicle is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Автомобиль с id={vehicle_id} не найден",
            )

        events = await self._tracking_dao.get_vehicle_history(vehicle_id, limit=limit)
        return VehicleRouteRead(
            vehicle_id=vehicle_id,
            plate_number=vehicle.plate_number,
            events=[self._event_to_read(e) for e in events],
            total_events=len(events),
        )


    @staticmethod
    def _to_read(vehicle: Vehicles) -> VehicleRead:
        return VehicleRead(
            id=vehicle.id,
            plate_number=vehicle.plate_number,
            is_inside=vehicle.is_inside,
            last_seen=vehicle.last_seen,
            last_camera_id=vehicle.last_camera_id,
        )

    @staticmethod
    def _event_to_read(event: Tracking) -> TrackingEventRead:
        from src.schemas import BoundingBox
        bbox = BoundingBox(**event.bbox) if event.bbox else None
        return TrackingEventRead(
            id=event.id,
            camera_id=event.camera_id,
            camera_position_x=None,  # загружается через join если нужно
            camera_position_y=None,
            spot_id=event.spot_id,
            event_type=event.event_type,
            timestamp=event.timestamp,
            bbox=bbox,
        )