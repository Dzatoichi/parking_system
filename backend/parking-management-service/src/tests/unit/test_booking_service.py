"""tests/unit/test_booking_service.py"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from src.models.status.booking_status import BookingStatus
from src.models.status.spot_status import SpotStatus
from src.schemas.booking_schemas import BookingCreate, BookingUpdate
from src.services.booking_service import BookingService


class _Spot:
    def __init__(
        self,
        spot_id: int = 1,
        parking_id: int = 10,
        status: SpotStatus = SpotStatus.FREE,
    ) -> None:
        self.id = spot_id
        self.parking_id = parking_id
        self.spot_number = "A-01"
        self.spot_type = "standard"
        self.spot_status = status
        self.spot_coordinates = {
            "points": [[0, 0], [1, 0], [1, 1], [0, 1]],
            "center_x": 0.5,
            "center_y": 0.5,
        }
        self.current_vehicle_id = None


class _Booking:
    def __init__(
        self,
        booking_id: int = 1,
        spot_id: int = 1,
        status: BookingStatus = BookingStatus.PENDING,
    ) -> None:
        now = datetime.now(tz=timezone.utc)
        self.id = booking_id
        self.user_id = 123
        self.spot_id = spot_id
        self.status = status
        self.start_time = now
        self.end_time = now + timedelta(hours=2)
        self.created_at = now
        self.updated_at = now
        self.notes = None
        self.cancellation_reason = None


def _make_service() -> tuple[BookingService, AsyncMock]:
    session = AsyncMock()
    session.commit = AsyncMock()
    async def _refresh(obj) -> None:
        now = datetime.now(tz=timezone.utc)
        if getattr(obj, "id", None) is None:
            obj.id = 1
        if getattr(obj, "created_at", None) is None:
            obj.created_at = now
        if getattr(obj, "updated_at", None) is None:
            obj.updated_at = now
    session.refresh = AsyncMock(side_effect=_refresh)
    session.add = Mock()
    service = BookingService(session)
    service._booking_dao = AsyncMock()
    service._spot_dao = AsyncMock()
    service._parking_dao = AsyncMock()
    service._sync_parking_available_spots = AsyncMock()
    service._sync_spot_status_after_booking_change = AsyncMock()
    return service, session


class TestCreateBooking:
    @pytest.mark.asyncio
    async def test_creates_booking_and_reserves_spot(self) -> None:
        service, session = _make_service()
        service._spot_dao.get_by_id.return_value = _Spot()
        service._booking_dao.get_conflicting_bookings.return_value = []

        result = await service.create_booking(
            BookingCreate(
                user_id=123,
                spot_id=1,
                start_time=datetime.now(tz=timezone.utc),
                end_time=datetime.now(tz=timezone.utc) + timedelta(hours=1),
            )
        )

        assert result.spot_id == 1
        service._spot_dao.update_status.assert_awaited_once_with(
            1,
            SpotStatus.RESERVED,
            vehicle_id=None,
        )
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_raises_404_when_spot_missing(self) -> None:
        service, _ = _make_service()
        service._spot_dao.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc:
            await service.create_booking(
                BookingCreate(
                    user_id=123,
                    spot_id=999,
                    start_time=datetime.now(tz=timezone.utc),
                    end_time=datetime.now(tz=timezone.utc) + timedelta(hours=1),
                )
            )

        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_raises_409_on_conflict(self) -> None:
        service, _ = _make_service()
        service._spot_dao.get_by_id.return_value = _Spot()
        service._booking_dao.get_conflicting_bookings.return_value = [_Booking()]

        with pytest.raises(HTTPException) as exc:
            await service.create_booking(
                BookingCreate(
                    user_id=123,
                    spot_id=1,
                    start_time=datetime.now(tz=timezone.utc),
                    end_time=datetime.now(tz=timezone.utc) + timedelta(hours=1),
                )
            )

        assert exc.value.status_code == 409


class TestUpdateBooking:
    @pytest.mark.asyncio
    async def test_confirms_pending_booking(self) -> None:
        service, session = _make_service()
        service._booking_dao.get_by_id.return_value = _Booking(status=BookingStatus.PENDING)

        result = await service.update_booking(
            1,
            BookingUpdate(status=BookingStatus.CONFIRMED),
        )

        assert result.status == BookingStatus.CONFIRMED
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cancels_booking_and_syncs_spot(self) -> None:
        service, session = _make_service()
        booking = _Booking(status=BookingStatus.CONFIRMED)
        service._booking_dao.get_by_id.return_value = booking
        service._sync_spot_status_after_booking_change = AsyncMock()

        result = await service.update_booking(
            1,
            BookingUpdate(
                status=BookingStatus.CANCELLED,
                cancellation_reason="user request",
            ),
        )

        assert result.status == BookingStatus.CANCELLED
        assert result.cancellation_reason == "user request"
        service._sync_spot_status_after_booking_change.assert_awaited_once_with(booking.spot_id)
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_raises_409_when_confirming_non_pending(self) -> None:
        service, _ = _make_service()
        service._booking_dao.get_by_id.return_value = _Booking(status=BookingStatus.CONFIRMED)

        with pytest.raises(HTTPException) as exc:
            await service.update_booking(
                1,
                BookingUpdate(status=BookingStatus.CONFIRMED),
            )

        assert exc.value.status_code == 409
