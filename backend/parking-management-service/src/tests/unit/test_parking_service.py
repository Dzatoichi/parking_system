"""tests/unit/test_parking_service.py"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi import HTTPException

from src.services.parking_service import ParkingService
from src.models.parkings import ParkingBase
from src.schemas import ParkingCreate, ParkingUpdate


def _make_orm_parking(
    parking_id: int = 1,
    name: str = "Тест-парковка",
    address: str = "ул. Ленина, 1",
    total_spots: int = 100,
    available_spots: int = 100,
    is_active: bool = True,
) -> ParkingBase:
    p = ParkingBase(
        name=name,
        address=address,
        total_spots=total_spots,
        available_spots=available_spots,
        is_active=is_active,
        coordinates=None,
        boundaries=None,
        settings={},
    )
    p.id = parking_id
    return p


def _make_service():
    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    service = ParkingService(mock_session)
    mock_dao = AsyncMock()
    service._dao = mock_dao
    return service, mock_session, mock_dao


# ── get_parking ──────────────────────────────────────────────

class TestGetParking:
    @pytest.mark.asyncio
    async def test_returns_parking_when_found(self):
        service, _, mock_dao = _make_service()
        mock_dao.get_by_id.return_value = _make_orm_parking()

        result = await service.get_parking(1)

        assert result.id == 1
        assert result.name == "Тест-парковка"

    @pytest.mark.asyncio
    async def test_raises_404_when_not_found(self):
        service, _, mock_dao = _make_service()
        mock_dao.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc:
            await service.get_parking(99)

        assert exc.value.status_code == 404


# ── create_parking ───────────────────────────────────────────

class TestCreateParking:
    def _make_data(self, name: str = "Новая") -> ParkingCreate:
        return ParkingCreate(name=name, address="ул. Тест, 5", total_spots=50)

    @pytest.mark.asyncio
    async def test_creates_parking_successfully(self):
        service, mock_session, mock_dao = _make_service()
        mock_dao.get_by_name.return_value = None
        mock_dao.create.return_value = _make_orm_parking(name="Новая")

        result = await service.create_parking(self._make_data("Новая"))

        assert result.name == "Новая"
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_raises_409_on_duplicate_name(self):
        service, _, mock_dao = _make_service()
        mock_dao.get_by_name.return_value = _make_orm_parking()

        with pytest.raises(HTTPException) as exc:
            await service.create_parking(self._make_data("Тест-парковка"))

        assert exc.value.status_code == 409
        mock_dao.create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_available_spots_equals_total_on_create(self):
        service, _, mock_dao = _make_service()
        mock_dao.get_by_name.return_value = None
        created = _make_orm_parking(total_spots=80, available_spots=80)
        mock_dao.create.return_value = created

        await service.create_parking(ParkingCreate(name="X", address="Y Y Y Y Y", total_spots=80))

        call_args = mock_dao.create.call_args[0][0]
        assert call_args.available_spots == call_args.total_spots


# ── update_parking ───────────────────────────────────────────

class TestUpdateParking:
    @pytest.mark.asyncio
    async def test_updates_fields(self):
        service, mock_session, mock_dao = _make_service()
        mock_dao.get_by_id.return_value = _make_orm_parking()
        updated = _make_orm_parking(is_active=False)
        mock_dao.update.return_value = updated

        result = await service.update_parking(1, ParkingUpdate(is_active=False))

        assert result.is_active is False
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_op_when_empty_update(self):
        service, mock_session, mock_dao = _make_service()
        mock_dao.get_by_id.return_value = _make_orm_parking()

        result = await service.update_parking(1, ParkingUpdate())

        mock_dao.update.assert_not_awaited()
        mock_session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_raises_404_when_not_found(self):
        service, _, mock_dao = _make_service()
        mock_dao.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc:
            await service.update_parking(99, ParkingUpdate(name="X"))

        assert exc.value.status_code == 404


# ── delete_parking ───────────────────────────────────────────

class TestDeleteParking:
    @pytest.mark.asyncio
    async def test_deletes_successfully(self):
        service, mock_session, mock_dao = _make_service()
        mock_dao.get_by_id.return_value = _make_orm_parking()
        mock_dao.delete.return_value = True

        await service.delete_parking(1)

        mock_dao.delete.assert_awaited_once_with(1)
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_raises_404_when_not_found(self):
        service, _, mock_dao = _make_service()
        mock_dao.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc:
            await service.delete_parking(99)

        assert exc.value.status_code == 404