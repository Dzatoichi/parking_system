from typing import Optional
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from src.dao.spot_dao import SpotDAO
from src.models.spots import Spot
from src.models.status.spot_status import SpotStatus
from src.models.type.spot_type import SpotType
from src.schemas import (
    SpotCreate,
    SpotRead,
    SpotReadShort,
    SpotOwnershipRegister,
    SpotRentalUpdate,
    SpotStatusUpdate,
    SpotCoordinatesUpdate,
    PaginatedResponse,
    ParkingStats,
)
from src.dao.parking_dao import ParkingDAO
from src.dao.event_dao import EventDAO
from src.services.system_event_ws import system_event_ws_manager


class SpotService:
    """
    Бизнес-логика для работы с парковочными местами.

    Принципы:
      - Сервис управляет транзакцией: он делает commit или rollback
      - DAO вызывается только отсюда — роутер не знает про SQL
      - Все ошибки — HTTPException с понятным detail
      - Методы возвращают Pydantic-схемы, а не ORM-объекты
    """

    def __init__(self, spot_dao: SpotDAO, parking_dao: ParkingDAO, event_dao: EventDAO | None = None) -> None:
        self._dao = spot_dao
        self._parking_dao = parking_dao
        self._event_dao = event_dao

    async def get_spot_by_id(self, spot_id: int) -> SpotRead:
        spot = await self._dao.get_by_id(spot_id)
        if spot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Место с id={spot_id} не найдено",
            )
        return SpotRead.model_validate(spot)



    async def get_spots_by_parking(
        self,
        parking_id: int,
        filter_status: Optional[SpotStatus] = None,
        filter_type: Optional[SpotType] = None,
        page: int = 1,
        size: int = 50,
    ) -> PaginatedResponse[SpotRead]:
        offset = (page - 1) * size
        spots, total = await self._dao.get_by_parking(
            parking_id=parking_id,
            status=filter_status,
            spot_type=filter_type,
            offset=offset,
            limit=size,
        )
        items = [SpotRead.model_validate(s) for s in spots]
        return PaginatedResponse.create(items=items, total=total, page=page, size=size)

    async def get_owner_spots(self, owner_id: int) -> list[SpotRead]:
        spots = await self._dao.get_by_owner(owner_id)
        return [SpotRead.model_validate(spot) for spot in spots]

    async def register_ownership(
        self,
        spot_id: int,
        owner_id: int,
        data: SpotOwnershipRegister,
    ) -> SpotRead:
        spot = await self._dao.get_by_id(spot_id)
        if spot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Место с id={spot_id} не найдено",
            )
        if spot.owner_id is not None and spot.owner_id != owner_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Место уже зарегистрировано на другого пользователя",
            )

        updated = await self._dao.update_rental_settings(
            spot_id,
            owner_id=owner_id,
            hourly_rate=data.hourly_rate,
            penalty=data.penalty,
            rental_enabled=data.rental_enabled,
            spot_status=SpotStatus.FREE if data.rental_enabled else SpotStatus.RESERVED,
        )
        return SpotRead.model_validate(updated)

    async def update_rental_settings(
        self,
        spot_id: int,
        owner_id: int,
        data: SpotRentalUpdate,
    ) -> SpotRead:
        spot = await self._dao.get_by_id(spot_id)
        if spot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Место с id={spot_id} не найдено",
            )
        if spot.owner_id != owner_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Можно управлять только своими местами",
            )

        new_status = data.status
        if new_status is None and data.rental_enabled is not None:
            new_status = SpotStatus.FREE if data.rental_enabled else SpotStatus.RESERVED

        updated = await self._dao.update_rental_settings(
            spot_id,
            hourly_rate=data.hourly_rate,
            penalty=data.penalty,
            rental_enabled=data.rental_enabled,
            spot_status=new_status,
        )
        return SpotRead.model_validate(updated)

    async def get_parking_stats(self, parking_id: int) -> ParkingStats:
        stats = await self._dao.get_stats(parking_id)
        total = stats["total"]
        occupied = stats["occupied"]

        return ParkingStats(
            parking_id=parking_id,
            total_spots=total,
            free=stats["free"],
            occupied=occupied,
            reserved=stats["reserved"],
            occupancy_rate=round(occupied / total, 4) if total > 0 else 0.0,
            avg_duration_minutes=None,  # TODO: считать из tracking_table
        )

    async def create_spot(self, parking_id: int, data: SpotCreate) -> SpotRead:
        # Проверяем уникальность номера места внутри парковки
        existing = await self._dao.get_by_number(parking_id, data.spot_number)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Место с номером '{data.spot_number}' уже существует на этой парковке",
            )

        # spot = Spot(
        #     parking_id=parking_id,
        #     spot_number=data.spot_number,
        #     spot_type=data.spot_type,
        #     spot_status=SpotStatus.FREE,
        #     spot_coordinates=data.spot_coordinates.model_dump(),
        # )
        spot_dict = {
            "parking_id": parking_id,
            "spot_number": data.spot_number,
            "spot_type": data.spot_type,
            "spot_status": SpotStatus.FREE,
            "spot_coordinates": data.spot_coordinates.model_dump(),
        }

        spot = await self._dao.create(spot_dict)
        return SpotRead.model_validate(spot)

    async def create_spots_bulk(
        self,
        parking_id: int,
        spots_data: list[SpotCreate],
    ) -> list[SpotRead]:
        """
        Пакетное создание мест — используется при первичной разметке парковки.
        Если хотя бы один номер занят — откатываем всё целиком.
        """
        # Проверяем дубли внутри самого запроса
        numbers = [s.spot_number for s in spots_data]
        if len(numbers) != len(set(numbers)):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="В запросе есть дублирующиеся номера мест",
            )

        # Проверяем конфликты с БД
        for spot_data in spots_data:
            existing = await self._dao.get_by_number(parking_id, spot_data.spot_number)
            if existing is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Место '{spot_data.spot_number}' уже существует, операция отменена",
                )

        spots = [
            Spot(
                parking_id=parking_id,
                spot_number=s.spot_number,
                spot_type=s.spot_type,
                spot_status=SpotStatus.FREE,
                spot_coordinates=s.spot_coordinates.model_dump(),
            )
            for s in spots_data
        ]

        created = await self._dao.create_bulk(spots)
        return [SpotRead.model_validate(s) for s in created]


    async def change_status(self, spot_id: int, data: SpotStatusUpdate) -> SpotRead:
        spot = await self._dao.get_by_id(spot_id)
        if spot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Место с id={spot_id} не найдено",
            )

        # Защита от бессмысленных переходов статуса
        if spot.spot_status == data.status:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Место уже имеет статус '{data.status.value}'",
            )

        # Нельзя занять место, которое уже занято другим авто
        if (
            data.status == SpotStatus.OCCUPIED
            and spot.current_vehicle_id is not None
            and spot.current_vehicle_id != data.vehicle_id
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Место занято другим автомобилем",
            )

        updated = await self._dao.update_status(
            spot_id=spot_id,
            new_status=data.status,
            vehicle_id=data.vehicle_id,
        )
        stats = await self._dao.get_stats(spot.parking_id)
        await self._parking_dao.update(spot.parking_id, available_spots=stats["free"])
        if self._event_dao is not None:
            event = await self._event_dao.create(
                {
                    "event_type": "spot_status_changed",
                    "entity_type": "spot",
                    "entity_id": spot_id,
                    "parking_id": spot.parking_id,
                    "message": "spot status",
                    "payload": {
                        "source": data.source or "api",
                        "previous_status": spot.spot_status.value,
                        "new_status": data.status.value,
                        "vehicle_id": data.vehicle_id,
                        **(data.payload or {}),
                    },
                }
            )
            await system_event_ws_manager.broadcast_event(event)
        return SpotRead.model_validate(updated)

    async def update_coordinates(
        self,
        spot_id: int,
        data: SpotCoordinatesUpdate,
    ) -> SpotRead:
        """
        Обновление разметки места после физического перемаркирования.
        Нельзя перемаркировать занятое место.
        """
        spot = await self._dao.get_by_id(spot_id)
        if spot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Место с id={spot_id} не найдено",
            )

        if spot.spot_status == SpotStatus.OCCUPIED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Нельзя изменить разметку занятого места",
            )

        updated = await self._dao.update_coordinates(
            spot_id=spot_id,
            coordinates=data.spot_coordinates.model_dump(),
        )
        return SpotRead.model_validate(updated)


    async def delete_spot(self, spot_id: int) -> None:
        spot = await self._dao.get_by_id(spot_id)
        if spot is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Место с id={spot_id} не найдено",
            )

        if spot.spot_status == SpotStatus.OCCUPIED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Нельзя удалить занятое место",
            )

        await self._dao.delete(spot_id)
