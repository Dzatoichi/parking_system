"""
tests/unit/test_spot_service.py

Unit-тесты сервиса — DAO полностью заменяется моком.
Тестируем только бизнес-логику SpotService: какие HTTPException бросает,
какие методы DAO вызывает и с какими аргументами.

Никакой БД не нужно — всё в памяти.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from src.services.spot_service import SpotService
from src.models.spots.spot import Spot
from src.models.spots.status.spot_status import SpotStatus
from src.models.spots.type.spot_type import SpotType
from src.schemas import SpotCreate, SpotStatusUpdate, SpotCoordinatesUpdate
from src.schemas.spot_schemas import SpotCoordinates


# ──────────────────────────────────────────────────────────────
# Вспомогательные фабрики
# ──────────────────────────────────────────────────────────────

def _make_orm_spot(
    spot_id: int = 1,
    parking_id: int = 1,
    spot_number: str = "A-01",
    spot_status: SpotStatus = SpotStatus.FREE,
    current_vehicle_id: int | None = None,
) -> Spot:
    spot = Spot(
        parking_id=parking_id,
        spot_number=spot_number,
        spot_type=SpotType.STANDARD,
        spot_status=spot_status,
        spot_coordinates={
            "points": [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]],
            "center_x": 5.0,
            "center_y": 5.0,
        },
        current_vehicle_id=current_vehicle_id,
    )
    spot.id = spot_id  # имитируем autoincrement из БД
    return spot


def _make_service() -> tuple[SpotService, MagicMock, AsyncMock]:
    """
    Создаёт SpotService с замоканными session и DAO.
    Возвращает (service, mock_session, mock_dao).
    """
    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()

    service = SpotService(mock_session)

    mock_dao = AsyncMock()
    service._dao = mock_dao  # подменяем DAO напрямую

    return service, mock_session, mock_dao


# ──────────────────────────────────────────────────────────────
# get_spot
# ──────────────────────────────────────────────────────────────

class TestGetSpot:
    @pytest.mark.asyncio
    async def test_returns_spot_when_found(self):
        service, _, mock_dao = _make_service()
        orm_spot = _make_orm_spot()
        mock_dao.get_by_id.return_value = orm_spot

        result = await service.get_spot(1)

        assert result.id == 1
        assert result.spot_number == "A-01"
        mock_dao.get_by_id.assert_awaited_once_with(1)

    @pytest.mark.asyncio
    async def test_raises_404_when_not_found(self):
        service, _, mock_dao = _make_service()
        mock_dao.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await service.get_spot(99)

        assert exc_info.value.status_code == 404
        assert "99" in exc_info.value.detail


# ──────────────────────────────────────────────────────────────
# get_parking_stats
# ──────────────────────────────────────────────────────────────

class TestGetParkingStats:
    @pytest.mark.asyncio
    async def test_calculates_occupancy_rate(self):
        service, _, mock_dao = _make_service()
        mock_dao.get_stats.return_value = {
            "free": 6,
            "occupied": 3,
            "reserved": 1,
            "total": 10,
        }

        result = await service.get_parking_stats(parking_id=1)

        assert result.total_spots == 10
        assert result.free == 6
        assert result.occupied == 3
        assert result.occupancy_rate == 0.3

    @pytest.mark.asyncio
    async def test_zero_occupancy_on_empty_parking(self):
        service, _, mock_dao = _make_service()
        mock_dao.get_stats.return_value = {
            "free": 0, "occupied": 0, "reserved": 0, "total": 0
        }

        result = await service.get_parking_stats(parking_id=1)

        # Деление на ноль не должно падать
        assert result.occupancy_rate == 0.0


# ──────────────────────────────────────────────────────────────
# create_spot
# ──────────────────────────────────────────────────────────────

class TestCreateSpot:
    def _make_spot_create(self, spot_number: str = "B-05") -> SpotCreate:
        return SpotCreate(
            spot_number=spot_number,
            spot_type=SpotType.STANDARD,
            spot_coordinates=SpotCoordinates(
                points=[[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]],
                center_x=5.0,
                center_y=5.0,
            ),
        )

    @pytest.mark.asyncio
    async def test_creates_spot_successfully(self):
        service, mock_session, mock_dao = _make_service()
        mock_dao.get_by_number.return_value = None  # номер свободен

        created_orm = _make_orm_spot(spot_number="B-05")
        mock_dao.create.return_value = created_orm

        result = await service.create_spot(parking_id=1, data=self._make_spot_create("B-05"))

        assert result.spot_number == "B-05"
        assert result.spot_status == SpotStatus.FREE
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_raises_409_on_duplicate_number(self):
        service, _, mock_dao = _make_service()
        mock_dao.get_by_number.return_value = _make_orm_spot()  # номер занят

        with pytest.raises(HTTPException) as exc_info:
            await service.create_spot(parking_id=1, data=self._make_spot_create("A-01"))

        assert exc_info.value.status_code == 409
        assert "A-01" in exc_info.value.detail
        mock_dao.create.assert_not_awaited()  # создание не должно было вызываться

    @pytest.mark.asyncio
    async def test_new_spot_always_starts_as_free(self):
        service, _, mock_dao = _make_service()
        mock_dao.get_by_number.return_value = None

        created_orm = _make_orm_spot(spot_status=SpotStatus.FREE)
        mock_dao.create.return_value = created_orm

        await service.create_spot(parking_id=1, data=self._make_spot_create())

        # Проверяем, что DAO получил объект со статусом FREE
        call_args = mock_dao.create.call_args[0][0]
        assert call_args.spot_status == SpotStatus.FREE


# ──────────────────────────────────────────────────────────────
# create_spots_bulk
# ──────────────────────────────────────────────────────────────

class TestCreateSpotsBulk:
    def _make_payload(self, numbers: list[str]) -> list[SpotCreate]:
        return [
            SpotCreate(
                spot_number=n,
                spot_type=SpotType.STANDARD,
                spot_coordinates=SpotCoordinates(
                    points=[[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]],
                    center_x=5.0,
                    center_y=5.0,
                ),
            )
            for n in numbers
        ]

    @pytest.mark.asyncio
    async def test_raises_422_on_duplicate_numbers_in_request(self):
        service, _, mock_dao = _make_service()

        with pytest.raises(HTTPException) as exc_info:
            await service.create_spots_bulk(
                parking_id=1,
                spots_data=self._make_payload(["A-01", "A-01"]),  # дубль
            )

        assert exc_info.value.status_code == 422
        mock_dao.get_by_number.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_raises_409_if_any_number_exists_in_db(self):
        service, _, mock_dao = _make_service()
        # Первый свободен, второй занят
        mock_dao.get_by_number.side_effect = [None, _make_orm_spot(spot_number="B-02")]

        with pytest.raises(HTTPException) as exc_info:
            await service.create_spots_bulk(
                parking_id=1,
                spots_data=self._make_payload(["A-01", "B-02"]),
            )

        assert exc_info.value.status_code == 409
        mock_dao.create_bulk.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_creates_all_spots_in_single_commit(self):
        service, mock_session, mock_dao = _make_service()
        mock_dao.get_by_number.return_value = None

        orm_spots = [_make_orm_spot(spot_number=n) for n in ["A-01", "A-02"]]
        mock_dao.create_bulk.return_value = orm_spots

        result = await service.create_spots_bulk(
            parking_id=1,
            spots_data=self._make_payload(["A-01", "A-02"]),
        )

        assert len(result) == 2
        mock_dao.create_bulk.assert_awaited_once()
        mock_session.commit.assert_awaited_once()  # ровно один commit


# ──────────────────────────────────────────────────────────────
# change_status
# ──────────────────────────────────────────────────────────────

class TestChangeStatus:
    @pytest.mark.asyncio
    async def test_free_to_occupied_sets_vehicle(self):
        service, mock_session, mock_dao = _make_service()
        mock_dao.get_by_id.return_value = _make_orm_spot(spot_status=SpotStatus.FREE)

        updated_orm = _make_orm_spot(spot_status=SpotStatus.OCCUPIED, current_vehicle_id=42)
        mock_dao.update_status.return_value = updated_orm

        result = await service.change_status(
            spot_id=1,
            data=SpotStatusUpdate(status=SpotStatus.OCCUPIED, vehicle_id=42),
        )

        assert result.spot_status == SpotStatus.OCCUPIED
        mock_dao.update_status.assert_awaited_once_with(
            spot_id=1, new_status=SpotStatus.OCCUPIED, vehicle_id=42
        )
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_raises_404_for_unknown_spot(self):
        service, _, mock_dao = _make_service()
        mock_dao.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await service.change_status(
                spot_id=999,
                data=SpotStatusUpdate(status=SpotStatus.FREE),
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_raises_409_on_same_status(self):
        service, _, mock_dao = _make_service()
        mock_dao.get_by_id.return_value = _make_orm_spot(spot_status=SpotStatus.FREE)

        with pytest.raises(HTTPException) as exc_info:
            await service.change_status(
                spot_id=1,
                data=SpotStatusUpdate(status=SpotStatus.FREE),
            )
        assert exc_info.value.status_code == 409
        assert "уже имеет статус" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_raises_409_when_occupied_by_another_vehicle(self):
        service, _, mock_dao = _make_service()
        mock_dao.get_by_id.return_value = _make_orm_spot(
            spot_status=SpotStatus.OCCUPIED,
            current_vehicle_id=10,  # занято авто #10
        )

        with pytest.raises(HTTPException) as exc_info:
            await service.change_status(
                spot_id=1,
                data=SpotStatusUpdate(status=SpotStatus.OCCUPIED, vehicle_id=99),  # другое авто
            )
        assert exc_info.value.status_code == 409
        assert "другим автомобилем" in exc_info.value.detail


# ──────────────────────────────────────────────────────────────
# update_coordinates
# ──────────────────────────────────────────────────────────────

class TestUpdateCoordinates:
    def _make_coords_update(self) -> SpotCoordinatesUpdate:
        return SpotCoordinatesUpdate(
            spot_coordinates=SpotCoordinates(
                points=[[1.0, 1.0], [9.0, 1.0], [9.0, 9.0], [1.0, 9.0]],
                center_x=5.0,
                center_y=5.0,
            )
        )

    @pytest.mark.asyncio
    async def test_updates_free_spot_successfully(self):
        service, mock_session, mock_dao = _make_service()
        mock_dao.get_by_id.return_value = _make_orm_spot(spot_status=SpotStatus.FREE)
        updated_orm = _make_orm_spot()
        mock_dao.update_coordinates.return_value = updated_orm

        await service.update_coordinates(spot_id=1, data=self._make_coords_update())

        mock_dao.update_coordinates.assert_awaited_once()
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_raises_409_for_occupied_spot(self):
        service, _, mock_dao = _make_service()
        mock_dao.get_by_id.return_value = _make_orm_spot(spot_status=SpotStatus.OCCUPIED)

        with pytest.raises(HTTPException) as exc_info:
            await service.update_coordinates(spot_id=1, data=self._make_coords_update())

        assert exc_info.value.status_code == 409
        mock_dao.update_coordinates.assert_not_awaited()


# ──────────────────────────────────────────────────────────────
# delete_spot
# ──────────────────────────────────────────────────────────────

class TestDeleteSpot:
    @pytest.mark.asyncio
    async def test_deletes_free_spot(self):
        service, mock_session, mock_dao = _make_service()
        mock_dao.get_by_id.return_value = _make_orm_spot(spot_status=SpotStatus.FREE)
        mock_dao.delete.return_value = True

        await service.delete_spot(spot_id=1)

        mock_dao.delete.assert_awaited_once_with(1)
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_raises_409_for_occupied_spot(self):
        service, _, mock_dao = _make_service()
        mock_dao.get_by_id.return_value = _make_orm_spot(spot_status=SpotStatus.OCCUPIED)

        with pytest.raises(HTTPException) as exc_info:
            await service.delete_spot(spot_id=1)

        assert exc_info.value.status_code == 409
        mock_dao.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_raises_404_when_not_found(self):
        service, _, mock_dao = _make_service()
        mock_dao.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await service.delete_spot(spot_id=404)

        assert exc_info.value.status_code == 404
