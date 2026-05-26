from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response, status, Query
from pydantic import BaseModel, Field

from src.models.status.booking_status import BookingStatus
from src.models.status.spot_status import SpotStatus
from src.models.type.spot_type import SpotType
from src.schemas.booking_schemas import BookingCreate, BookingRead, BookingUpdate
from src.schemas.spot_schemas import SpotStatusUpdate
from src.schemas.vehicle_schemas import VehicleCreate, VehicleRead
from src.schemas.parking_schemas import ParkingRead
from src.schemas.vehicle_schemas import MobileVehicleCreate
from src.schemas.common import PaginatedResponse
from src.utils.dependencies import (
    BookingServiceDep,
    ParkingServiceDep,
    SpotServiceDep,
    VehicleServiceDep,
    get_current_user_id,
)

mobile_compat_router = APIRouter(tags=["mobile compat"])


class MobileBookingCreate(BaseModel):
    start_time: datetime
    end_time: datetime
    user_id: int | None = Field(default=None, gt=0)
    parking_id: int | None = Field(default=None, gt=0)
    parking_spot: int | None = Field(default=None, gt=0)
    parking_spot_id: int | None = Field(default=None, gt=0)
    car_id: int | None = Field(default=None)
    hourly_rate: float | None = Field(default=None)
    total_cost: float | None = Field(default=None)
    penalty: float | None = Field(default=None)


class MobileSpotUpdate(BaseModel):
    status: int | bool | None = None
    hourly_rate: float | None = None
    penalty: float | None = None


def _spot_status_to_mobile(status_value: SpotStatus) -> int:
    return 1 if status_value == SpotStatus.FREE else 2


def _booking_status_to_mobile(status_value: BookingStatus) -> int:
    return {
        BookingStatus.PENDING: 1,
        BookingStatus.CONFIRMED: 2,
        BookingStatus.COMPLETED: 3,
        BookingStatus.CANCELLED: 4,
        BookingStatus.EXPIRED: 5,
    }[status_value]


def _parking_to_mobile(parking) -> dict[str, Any]:
    coordinates = parking.coordinates or {}
    return {
        "id": parking.id,
        "name": parking.name,
        "address": parking.address,
        "capacity": parking.total_spots,
        "latitude": coordinates.get("lat"),
        "longitude": coordinates.get("lng"),
        "createdAt": None,
        "updatedAt": None,
        "deletedAt": None,
        "isDeleted": not parking.is_active,
        "detail": None,
    }


def _spot_to_mobile(spot) -> dict[str, Any]:
    mobile_name_by_id = {
        12: "053",
        13: "016",
    }
    return {
        "id": spot.id,
        "name": mobile_name_by_id.get(spot.id, spot.spot_number),
        "user_id": None,
        "parking_id": spot.parking_id,
        "hourly_rate": 100,
        "for_disabled": spot.spot_type == SpotType.DISABLED,
        "availability_start_time": None,
        "availability_end_time": None,
        "penalty": 0,
        "created_at": None,
        "updated_at": None,
        "is_deleted": False,
        "status": _spot_status_to_mobile(spot.spot_status),
    }


def _vehicle_to_mobile(vehicle) -> dict[str, Any]:
    return {
        "id": vehicle.id,
        "brand_id": None,
        "number_plate": vehicle.plate_number,
        "name": vehicle.plate_number,
        "body_type_id": None,
        "created_at": None,
        "updated_at": None,
        "detail": None,
    }


async def _booking_to_mobile(
    booking: BookingRead,
    spot_service: SpotServiceDep,
    *,
    car_id: int | None = None,
    total_cost: float | None = None,
) -> dict[str, Any]:
    spot = await spot_service.get_spot_by_id(booking.spot_id)
    return {
        "id": booking.id,
        "start_time": booking.start_time.isoformat(),
        "end_time": booking.end_time.isoformat(),
        "actual_end_time": booking.end_time.isoformat() if booking.status == BookingStatus.COMPLETED else None,
        "planned_start_time": booking.start_time.isoformat(),
        "status": _booking_status_to_mobile(booking.status),
        "parking_id": spot.parking_id,
        "owner_id": None,
        "user_id": booking.user_id,
        "car_id": car_id or 0,
        "parking_spot": booking.spot_id,
        "parking_spot_id": booking.spot_id,
        "spot_name": spot.spot_number,
        "hourly_rate": 100,
        "total_cost": total_cost or 0,
        "penalty": 0,
        "created_at": booking.created_at.isoformat(),
        "updated_at": booking.updated_at.isoformat(),
        "expired_at": booking.end_time.isoformat(),
        "parking_name": None,
        "parking_address": None,
        "car_number_plate": None,
        "car_name": None,
        "detail": None,
    }


@mobile_compat_router.get("/parking/get/{parking_id}")
async def get_parking_info(
    parking_id: int,
    service: ParkingServiceDep,
) -> dict[str, Any]:
    parking = await service.get_parking(parking_id)
    return _parking_to_mobile(parking)


@mobile_compat_router.get("/spot/parking/{parking_id}")
async def get_parking_spots(
    parking_id: int,
    service: SpotServiceDep,
) -> dict[str, Any]:
    spots = await service.get_spots_by_parking(parking_id=parking_id, page=1, size=200)
    items = [_spot_to_mobile(spot) for spot in spots.items]
    return {"data": items, "totalCount": spots.total, "detail": None}


@mobile_compat_router.post("/spot/parking/{parking_id}")
async def post_parking_spots(
    parking_id: int,
    service: SpotServiceDep,
) -> dict[str, Any]:
    return await get_parking_spots(parking_id, service)


@mobile_compat_router.get("/spot/me")
async def get_renter_spots(service: SpotServiceDep) -> dict[str, Any]:
    spots = await service.get_spots_by_parking(parking_id=1, page=1, size=200)
    items = [_spot_to_mobile(spot) for spot in spots.items]
    return {"data": items, "totalCount": spots.total, "detail": None}


@mobile_compat_router.patch("/spot/update/{spot_id}", status_code=status.HTTP_200_OK)
async def update_mobile_spot(
    spot_id: int,
    body: MobileSpotUpdate,
    service: SpotServiceDep,
) -> Response:
    if body.status is not None:
        new_status = SpotStatus.FREE if body.status in (1, True) else SpotStatus.RESERVED
        current = await service.get_spot_by_id(spot_id)
        if current.spot_status != new_status:
            await service.change_status(spot_id, SpotStatusUpdate(status=new_status, vehicle_id=None))
    return Response(status_code=status.HTTP_200_OK)


@mobile_compat_router.get("/cars/me")
async def get_my_cars(
    service: VehicleServiceDep,
    user_id: int = Depends(get_current_user_id),
) -> dict[str, Any]:
    vehicles = await service.get_vehicle_me(owner_id=user_id)
    items = [_vehicle_to_mobile(vehicle) for vehicle in vehicles]
    if not items:
        items.append(
            {
                "id": 0,
                "brand_id": None,
                "number_plate": "",
                "name": "Demo car",
                "body_type_id": None,
                "created_at": None,
                "updated_at": None,
                "detail": None,
            }
        )
    return {"data": items, "totalCount": len(items), "detail": None}


@mobile_compat_router.post("/booking/create")
async def create_mobile_booking(
    body: MobileBookingCreate,
    booking_service: BookingServiceDep,
    spot_service: SpotServiceDep,
    user_id: int = Depends(get_current_user_id),
) -> dict[str, Any]:
    spot_id = body.parking_spot_id or body.parking_spot
    if spot_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="parking_spot or parking_spot_id is required",
        )
    booking = await booking_service.create_booking(
        BookingCreate(
            user_id=body.user_id or user_id,
            spot_id=spot_id,
            start_time=body.start_time,
            end_time=body.end_time,
        )
    )
    return await _booking_to_mobile(
        booking,
        spot_service,
        car_id=body.car_id,
        total_cost=body.total_cost,
    )


@mobile_compat_router.get("/booking/get/{booking_id}")
async def get_mobile_booking(
    booking_id: int,
    booking_service: BookingServiceDep,
    spot_service: SpotServiceDep,
) -> dict[str, Any]:
    booking = await booking_service.get_booking(booking_id)
    return await _booking_to_mobile(booking, spot_service)


@mobile_compat_router.get("/booking/me")
async def get_mobile_current_booking(
    booking_service: BookingServiceDep,
    spot_service: SpotServiceDep,
    user_id: int = Depends(get_current_user_id),
) -> dict[str, Any]:
    bookings = await booking_service.get_user_bookings(user_id=user_id, page=1, size=20)
    for booking in bookings.items:
        if booking.status in {BookingStatus.PENDING, BookingStatus.CONFIRMED}:
            return await _booking_to_mobile(booking, spot_service)
    return {"detail": "Активное бронирование не найдено"}


@mobile_compat_router.post("/booking/pay/{booking_id}")
async def pay_mobile_booking(
    booking_id: int,
    booking_service: BookingServiceDep,
    spot_service: SpotServiceDep,
) -> dict[str, Any]:
    booking = await booking_service.update_booking(
        booking_id,
        BookingUpdate(status=BookingStatus.CONFIRMED),
    )
    mobile_booking = await _booking_to_mobile(booking, spot_service)
    return {
        "id": mobile_booking["id"],
        "planned_start_time": mobile_booking["start_time"],
        "planned_end_time": mobile_booking["end_time"],
        "actual_end_time": None,
        "status": mobile_booking["status"],
        "user_id": mobile_booking["user_id"],
        "owner_id": mobile_booking["owner_id"],
        "parking_id": mobile_booking["parking_id"],
        "car_id": mobile_booking["car_id"],
        "hourly_rate": mobile_booking["hourly_rate"],
        "penalty": mobile_booking["penalty"],
        "total_cost": mobile_booking["total_cost"],
        "created_at": mobile_booking["created_at"],
        "updated_at": mobile_booking["updated_at"],
        "is_deleted": False,
        "detail": None,
    }


@mobile_compat_router.post("/booking/reject/{booking_id}")
async def reject_mobile_booking(
    booking_id: int,
    booking_service: BookingServiceDep,
) -> bool:
    await booking_service.update_booking(
        booking_id,
        BookingUpdate(status=BookingStatus.CANCELLED, cancellation_reason="mobile user rejected booking"),
    )
    return True


@mobile_compat_router.get("/rental/get/{booking_id}")
async def get_mobile_rental(
    booking_id: int,
    booking_service: BookingServiceDep,
    spot_service: SpotServiceDep,
) -> dict[str, Any]:
    booking = await booking_service.get_booking(booking_id)
    return await _booking_to_mobile(booking, spot_service)


@mobile_compat_router.post("/rental/finish/{booking_id}")
async def finish_mobile_rental(
    booking_id: int,
    booking_service: BookingServiceDep,
) -> bool:
    await booking_service.update_booking(
        booking_id,
        BookingUpdate(status=BookingStatus.COMPLETED),
    )
    return True

@mobile_compat_router.post(path="/cars/add", response_model=VehicleRead, status_code=status.HTTP_201_CREATED)
async def register_vehicle(
    body: MobileVehicleCreate,
    service: VehicleServiceDep,
    owner_id: int = Depends(get_current_user_id),
) -> VehicleRead:
    return await service.register_vehicle(body, owner_id)

@mobile_compat_router.get(path="/parking/list", response_model=PaginatedResponse[ParkingRead])
async def get_parkings(
    service: ParkingServiceDep,
    only_active: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
) -> PaginatedResponse[ParkingRead]:
    return await service.get_all_parkings(only_active=only_active, page=page, size=size)

@mobile_compat_router.get(path="booking/active")
async def get_active_booking(
    booking_service: BookingServiceDep,
    spot_service: SpotServiceDep,
    user_id: int = Depends(get_current_user_id),
) -> dict[str, Any]:
    # то же что /booking/me — алиас для совместимости
    bookings = await booking_service.get_user_bookings(user_id=user_id, page=1, size=20)
    for booking in bookings.items:
        if booking.status in {BookingStatus.PENDING, BookingStatus.CONFIRMED}:
            return await _booking_to_mobile(booking, spot_service)
    raise HTTPException(status_code=404, detail="Активное бронирование не найдено")