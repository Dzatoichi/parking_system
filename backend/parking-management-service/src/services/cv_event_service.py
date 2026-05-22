from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from src.database.base import db_helper
from src.models.booking import Booking
from src.models.cv_geometry import CVSpotObservation
from src.models.spots import Spot
from src.models.status.booking_status import BookingStatus
from src.models.status.spot_status import SpotStatus
from src.models.system_events import SystemEvent
from src.models.tracking import Tracking
from src.models.vehicles import Vehicles


class CVEventService:
    async def apply_event(self, payload: dict[str, Any]) -> None:
        event_type = payload.get("event_type")
        if event_type in {"vehicle.detected", "vehicle.track_started"}:
            await self._record_observation(payload)
            return
        if event_type == "spot.occupied_confirmed":
            await self._handle_spot_occupied(payload)
            return
        if event_type == "spot.free_confirmed":
            await self._handle_spot_free(payload)
            return
        await self._record_observation(payload)

    async def _handle_spot_occupied(self, payload: dict[str, Any]) -> None:
        async with db_helper.async_session_maker() as session:
            async with session.begin():
                spot = await self._get_spot_for_update(session, payload["spot_id"])
                previous_status = spot.spot_status
                vehicle = await self._resolve_vehicle(session, payload)

                session.add(self._observation(payload))
                if previous_status != SpotStatus.OCCUPIED or spot.current_vehicle_id != vehicle.id:
                    spot.spot_status = SpotStatus.OCCUPIED
                    spot.current_vehicle_id = vehicle.id
                    spot.occupied_since = self._parse_timestamp(payload)

                vehicle.is_inside = True
                vehicle.last_camera_id = payload["camera_id"]
                vehicle.last_seen = self._parse_timestamp(payload).replace(tzinfo=None)

                session.add(
                    Tracking(
                        vehicle_id=vehicle.id,
                        camera_id=payload["camera_id"],
                        spot_id=spot.id,
                        timestamp=self._parse_timestamp(payload),
                        event_type="park",
                        bbox=payload.get("bbox"),
                    )
                )
                session.add(
                    self._system_event(
                        payload,
                        event_type="spot_status_changed",
                        entity_type="spot",
                        entity_id=spot.id,
                        message="spot occupied",
                        extra={
                            "previous_status": previous_status.value,
                            "new_status": SpotStatus.OCCUPIED.value,
                            "vehicle_id": vehicle.id,
                        },
                    )
                )
                await self._record_booking_mismatch(session, spot, vehicle, payload)
                await self._sync_available_spots(session, spot.parking_id)

    async def _handle_spot_free(self, payload: dict[str, Any]) -> None:
        async with db_helper.async_session_maker() as session:
            async with session.begin():
                spot = await self._get_spot_for_update(session, payload["spot_id"])
                previous_status = spot.spot_status
                previous_vehicle_id = spot.current_vehicle_id
                active_bookings = await self._active_bookings(session, spot.id, self._parse_timestamp(payload))
                new_status = SpotStatus.RESERVED if active_bookings else SpotStatus.FREE

                session.add(self._observation(payload))
                spot.spot_status = new_status
                spot.current_vehicle_id = None
                spot.occupied_since = None

                if previous_vehicle_id is not None:
                    session.add(
                        Tracking(
                            vehicle_id=previous_vehicle_id,
                            camera_id=payload["camera_id"],
                            spot_id=spot.id,
                            timestamp=self._parse_timestamp(payload),
                            event_type="leave_spot",
                            bbox=payload.get("bbox"),
                        )
                    )

                session.add(
                    self._system_event(
                        payload,
                        event_type="spot_status_changed",
                        entity_type="spot",
                        entity_id=spot.id,
                        message="spot free",
                        extra={
                            "previous_status": previous_status.value,
                            "new_status": new_status.value,
                            "previous_vehicle_id": previous_vehicle_id,
                        },
                    )
                )
                await self._sync_available_spots(session, spot.parking_id)

    async def _record_observation(self, payload: dict[str, Any]) -> None:
        async with db_helper.async_session_maker() as session:
            async with session.begin():
                session.add(self._observation(payload))

    async def _get_spot_for_update(self, session, spot_id: int) -> Spot:
        result = await session.execute(select(Spot).where(Spot.id == spot_id).with_for_update())
        spot = result.scalar_one_or_none()
        if spot is None:
            raise ValueError(f"Spot not found: {spot_id}")
        return spot

    async def _resolve_vehicle(self, session, payload: dict[str, Any]) -> Vehicles:
        vehicle_id = payload.get("vehicle_id")
        if vehicle_id is not None:
            vehicle = await session.get(Vehicles, int(vehicle_id))
            if vehicle is not None:
                return vehicle

        plate = payload.get("plate_number") or self._cv_plate(payload.get("cv_track_id"))
        result = await session.execute(select(Vehicles).where(Vehicles.plate_number == plate))
        vehicle = result.scalar_one_or_none()
        if vehicle is not None:
            return vehicle

        vehicle = Vehicles(plate_number=plate, owner_id=1, is_inside=True, is_blocked=False)
        session.add(vehicle)
        await session.flush()
        return vehicle

    async def _record_booking_mismatch(self, session, spot: Spot, vehicle: Vehicles, payload: dict[str, Any]) -> None:
        active_bookings = await self._active_bookings(session, spot.id, self._parse_timestamp(payload))
        for booking in active_bookings:
            if booking.vehicle_id is not None and booking.vehicle_id != vehicle.id:
                session.add(
                    self._system_event(
                        payload,
                        event_type="booking_conflict",
                        entity_type="booking",
                        entity_id=booking.id,
                        message="booking mismatch",
                        extra={
                            "booking_vehicle_id": booking.vehicle_id,
                            "actual_vehicle_id": vehicle.id,
                            "spot_id": spot.id,
                        },
                    )
                )
            elif booking.vehicle_id is None:
                session.add(
                    self._system_event(
                        payload,
                        event_type="booking_conflict",
                        entity_type="booking",
                        entity_id=booking.id,
                        message="unknown vehicle",
                        extra={"actual_vehicle_id": vehicle.id, "spot_id": spot.id},
                    )
                )

    async def _active_bookings(self, session, spot_id: int, now: datetime) -> list[Booking]:
        result = await session.execute(
            select(Booking).where(
                Booking.spot_id == spot_id,
                Booking.status.in_([BookingStatus.PENDING, BookingStatus.CONFIRMED]),
                Booking.end_time > now,
            )
        )
        return list(result.scalars().all())

    async def _sync_available_spots(self, session, parking_id: int) -> None:
        from src.models.parkings import ParkingBase

        result = await session.execute(select(Spot).where(Spot.parking_id == parking_id))
        spots = list(result.scalars().all())
        parking = await session.get(ParkingBase, parking_id)
        if parking is not None:
            parking.available_spots = sum(1 for spot in spots if spot.spot_status == SpotStatus.FREE)

    def _observation(self, payload: dict[str, Any]) -> CVSpotObservation:
        return CVSpotObservation(
            event_id=payload["event_id"],
            event_type=payload["event_type"],
            parking_id=payload["parking_id"],
            camera_id=payload["camera_id"],
            spot_id=payload.get("spot_id"),
            cv_track_id=payload.get("cv_track_id"),
            bbox=payload.get("bbox"),
            confidence=payload.get("confidence"),
            observed_at=self._parse_timestamp(payload),
            payload=payload,
        )

    def _system_event(
        self,
        payload: dict[str, Any],
        *,
        event_type: str,
        entity_type: str,
        entity_id: int,
        message: str,
        extra: dict[str, Any],
    ) -> SystemEvent:
        event_payload = dict(payload)
        event_payload.update(extra)
        return SystemEvent(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            parking_id=payload["parking_id"],
            message=message[:30],
            payload=event_payload,
        )

    @staticmethod
    def _parse_timestamp(payload: dict[str, Any]) -> datetime:
        raw = payload.get("timestamp")
        if not raw:
            return datetime.now(tz=timezone.utc)
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))

    @staticmethod
    def _cv_plate(cv_track_id: str | None) -> str:
        suffix = (cv_track_id or "UNKNOWN").replace("-", "")[:8].upper()
        return f"CV{suffix}"[:12]
