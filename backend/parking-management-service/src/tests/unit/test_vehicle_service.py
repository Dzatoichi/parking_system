"""tests/unit/test_vehicle_service.py"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from fastapi import HTTPException

from src.services.vehicle_service import VehicleService
from src.models.vehicles import Vehicles
from src.schemas import VehicleCreate, VehicleLocationUpdate, BoundingBox


def _make_vehicle(
    vehicle_id: int = 1,
    plate: str = "А123ВС77",
    is_inside: bool = False,
) -> Vehicles:
    v = Vehicles(plate_number=plate, is_inside=is_inside)
    v.id = vehicle_id
    v.last_seen = None
    v.last_camera_id = None
    return v


def _make_service():
    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    service = VehicleService(mock_session)
    service._dao = AsyncMock()
    service._tracking_dao = AsyncMock()
    return service, mock_session


# ── register_vehicle ─────────────────────────────────────────

class TestRegisterVehicle:
    @pytest.mark.asyncio
    async def test_registers_successfully(self):
        service, mock_session = _make_service()
        service._dao.get_by_plate.return_value = None
        service._dao.create.return_value = _make_vehicle(plate="B456CD")

        result = await service.register_vehicle(VehicleCreate(plate_number="B456CD"))

        assert result.plate_number == "B456CD"
        assert result.is_inside is False
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_raises_409_on_duplicate_plate(self):
        service, _ = _make_service()
        service._dao.get_by_plate.return_value = _make_vehicle()

        with pytest.raises(HTTPException) as exc:
            await service.register_vehicle(VehicleCreate(plate_number="А123ВС77"))

        assert exc.value.status_code == 409
        service._dao.create.assert_not_awaited()


# ── process_location_event ───────────────────────────────────

class TestProcessLocationEvent:
    def _make_event(self, event_type: str = "park", plate: str = "А123ВС77") -> VehicleLocationUpdate:
        return VehicleLocationUpdate(
            plate_number=plate,
            camera_id=1,
            bbox=BoundingBox(x1=0, y1=0, x2=100, y2=100),
            event_type=event_type,
            timestamp=datetime.now(tz=timezone.utc),
        )

    @pytest.mark.asyncio
    async def test_registers_new_vehicle_automatically(self):
        service, mock_session = _make_service()
        service._dao.get_by_plate.return_value = None  # неизвестное авто
        new_vehicle = _make_vehicle()
        service._dao.create.return_value = new_vehicle
        service._tracking_dao.create_event.return_value = object()

        await service.process_location_event(self._make_event())

        service._dao.create.assert_awaited_once()
        service._tracking_dao.create_event.assert_awaited_once()
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_sets_is_inside_true_on_enter(self):
        service, _ = _make_service()
        service._dao.get_by_plate.return_value = None
        new_vehicle = _make_vehicle(is_inside=True)
        service._dao.create.return_value = new_vehicle
        service._tracking_dao.create_event.return_value = object()

        result = await service.process_location_event(self._make_event("enter"))
        assert result.is_inside is True

    @pytest.mark.asyncio
    async def test_updates_existing_vehicle_on_exit(self):
        service, mock_session = _make_service()
        existing = _make_vehicle(is_inside=True)
        service._dao.get_by_plate.return_value = existing

        updated = _make_vehicle(is_inside=False)
        service._dao.update_location.return_value = updated
        service._tracking_dao.create_event.return_value = object()

        result = await service.process_location_event(self._make_event("exit"))

        assert result.is_inside is False
        service._dao.update_location.assert_awaited_once()
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_creates_tracking_event_always(self):
        service, _ = _make_service()
        service._dao.get_by_plate.return_value = None
        service._dao.create.return_value = _make_vehicle()
        service._tracking_dao.create_event.return_value = object()

        await service.process_location_event(self._make_event("pass"))

        service._tracking_dao.create_event.assert_awaited_once()


# ── delete_vehicle ───────────────────────────────────────────

class TestDeleteVehicle:
    @pytest.mark.asyncio
    async def test_deletes_vehicle_not_inside(self):
        service, mock_session = _make_service()
        service._dao.get_by_id.return_value = _make_vehicle(is_inside=False)
        service._dao.delete.return_value = True

        await service.delete_vehicle(1)

        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_raises_409_if_vehicle_is_inside(self):
        service, _ = _make_service()
        service._dao.get_by_id.return_value = _make_vehicle(is_inside=True)

        with pytest.raises(HTTPException) as exc:
            await service.delete_vehicle(1)

        assert exc.value.status_code == 409
        service._dao.delete.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_raises_404_when_not_found(self):
        service, _ = _make_service()
        service._dao.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc:
            await service.delete_vehicle(99)

        assert exc.value.status_code == 404