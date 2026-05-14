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
    VehicleBlockUpdate,
    VehicleLocationUpdate,
    VehicleRouteRead,
    TrackingEventRead,
    VehicleFullInfo,
    PaginatedResponse,
)


class VehicleService:
    def __init__(self, vehicle_dao: VehicleDAO, tracking_dao: TrackingDAO) -> None:
        self._dao = vehicle_dao
        self._tracking_dao = tracking_dao


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

    async def get_vehicle_me(
            self,
            owner_id: int
    ) -> list[VehicleRead] | None:
        vehicles = await self._dao.get_vehicle_me(owner_id)
        if vehicles is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Автомобиль с пользователем id={owner_id} не найден",
            )
        return [self._to_read(v) for v in vehicles]


    async def get_all_vehicles(
        self,
        only_inside: bool = False,
        page: int = 1,
        size: int = 50,
    ) -> PaginatedResponse[VehicleRead]:
        offset = (page - 1) * size
        vehicles, total = await self._dao.get_all_vehicles(
            only_inside=only_inside, offset=offset, limit=size
        )
        items = [self._to_read(v) for v in vehicles]
        return PaginatedResponse.create(items=items, total=total, page=page, size=size)


    async def register_vehicle(self, data: VehicleCreate, owner_id: int) -> VehicleRead:
        existing = await self._dao.get_by_plate(data.plate_number)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Автомобиль '{data.plate_number}' уже зарегистрирован",
            )

        # vehicle = Vehicles(
        #     plate_number=data.plate_number,
        #     owner_id=owner_id,
        #     is_inside=False,
        # )
        vehicle_dict = {
            "plate_number": data.plate_number,
            "owner_id": owner_id,
            "is_inside": False,
        }
        vehicle = await self._dao.create(vehicle_dict)
        return self._to_read(vehicle)

    async def process_location_event(self, data: VehicleLocationUpdate) -> VehicleRead:
        """
        Обрабатывает событие от CV-сервиса: регистрирует авто если новое,
        обновляет местоположение и создаёт запись в tracking.
        """
        vehicle = await self._dao.get_by_plate(data.plate_number)

        # Авто видим впервые — регистрируем автоматически
        if vehicle is None:
            if data.event_type == "enter":
                # Для незарегистрированного авто не блокируем вход автоматически.
                pass
            # vehicle = Vehicles(
            #     plate_number=data.plate_number,
            #     is_inside=data.event_type == "enter",
            # )
            vehicle_dict = {
                "plate_number": data.plate_number,
                "is_inside": data.event_type == "enter",
            }
            vehicle = await self._dao.create(vehicle_dict)
        else:
            if vehicle.is_blocked and data.event_type == "enter":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Въезд запрещен для автомобиля '{vehicle.plate_number}'",
                )
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

        event_dict = {
            "vehicle_id": vehicle.id,
            "camera_id": data.camera_id,
            "spot_id": data.spot_id,
            "timestamp": data.timestamp or datetime.now(tz=timezone.utc),
            "event_type": data.event_type,
            "bbox": data.bbox.model_dump() if data.bbox else None,
        }
        await self._tracking_dao.create(event_dict)

        return self._to_read(vehicle)

    async def set_vehicle_block_by_plate(
        self,
        plate_number: str,
        body: VehicleBlockUpdate,
    ) -> VehicleRead:
        vehicle = await self._dao.get_by_plate(plate_number.upper())
        if vehicle is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Автомобиль с номером '{plate_number}' не найден",
            )
        updated = await self._dao.set_blocked(vehicle.id, body.blocked)
        return self._to_read(updated)

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

    async def get_vehicle_full_info(
        self,
        vehicle_id: int,
        limit: int = 100,
    ) -> VehicleFullInfo:
        """
        Агрегированная информация об авто:
        - базовые данные (номер, статус, последняя камера)
        - история перемещений (последние N событий).
        """
        vehicle = await self._dao.get_by_id(vehicle_id)
        if vehicle is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Автомобиль с id={vehicle_id} не найден",
            )

        events = await self._tracking_dao.get_vehicle_history(vehicle_id, limit=limit)
        history = VehicleRouteRead(
            vehicle_id=vehicle.id,
            plate_number=vehicle.plate_number,
            events=[self._event_to_read(e) for e in events],
            total_events=len(events),
        )

        return VehicleFullInfo(
            vehicle=self._to_read(vehicle),
            history=history,
        )


    @staticmethod
    def _to_read(vehicle: Vehicles) -> VehicleRead:
        return VehicleRead(
            id=vehicle.id,
            plate_number=vehicle.plate_number,
            owner_id=vehicle.owner_id,
            is_inside=bool(vehicle.is_inside),
            is_blocked=bool(getattr(vehicle, "is_blocked", False) or False),
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
