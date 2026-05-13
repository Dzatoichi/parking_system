from datetime import datetime

from src.clients.auth_client import AuthServiceClient
from src.dao.booking_dao import BookingDAO
from src.dao.booking_projection_dao import BookingProjectionDAO
from src.models.booking import Booking
from src.models.status.booking_status import BookingStatus


class BookingProjectionService:
    def __init__(
        self,
        projection_dao: BookingProjectionDAO,
        booking_dao: BookingDAO,
        auth_client: AuthServiceClient,
    ) -> None:
        self._projection_dao = projection_dao
        self._booking_dao = booking_dao
        self._auth_client = auth_client

    async def rebuild_projection(self) -> None:
        bookings = await self._booking_dao.get_all_with_spot()
        payloads = []
        for booking in bookings:
            payloads.append(await self._serialize_booking(booking))
        await self._projection_dao.replace_all(payloads)

    async def apply_event(self, payload: dict) -> None:
        user_name = payload.get("user_name")
        if not user_name:
            user = await self._auth_client.get_user_by_id(payload["user_id"])
            user_name = user.get("full_name") if user else None
            if not user_name and user:
                user_name = user.get("email")

        await self._projection_dao.upsert(
            {
                "booking_id": payload["booking_id"],
                "parking_id": payload["parking_id"],
                "user_id": payload["user_id"],
                "user_name": user_name,
                "spot_id": payload["spot_id"],
                "spot_number": payload["spot_number"],
                "status": BookingStatus(payload["status"]),
                "start_time": datetime.fromisoformat(payload["start_time"]),
                "end_time": datetime.fromisoformat(payload["end_time"]),
                "created_at": datetime.fromisoformat(payload["created_at"]),
                "updated_at": datetime.fromisoformat(payload["updated_at"]),
            }
        )

    async def _serialize_booking(self, booking: Booking) -> dict:
        user = await self._auth_client.get_user_by_id(booking.user_id)
        user_name = None
        if user:
            user_name = user.get("full_name") or user.get("email")

        return {
            "booking_id": booking.id,
            "parking_id": booking.spot.parking_id,
            "user_id": booking.user_id,
            "user_name": user_name,
            "spot_id": booking.spot_id,
            "spot_number": booking.spot.spot_number,
            "status": booking.status,
            "start_time": booking.start_time,
            "end_time": booking.end_time,
            "created_at": booking.created_at,
            "updated_at": booking.updated_at,
        }
