"""
src/utils/dependencies.py

Единое место для всех FastAPI-зависимостей проекта.
Правило: роутеры импортируют только отсюда — никаких локальных Depends.
"""

from typing import Annotated

from fastapi import Depends, security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.auth_client import AuthServiceClient
from src.dao.booking_dao import BookingDAO
from src.dao.camera_dao import CameraDAO
from src.dao.parking_dao import ParkingDAO
from src.dao.spot_dao import SpotDAO
from src.dao.vehicle_dao import VehicleDAO, TrackingDAO
from src.database.base import db_helper
from src.services.booking_service import BookingService
from src.services.spot_service import SpotService
from src.services.parking_service import ParkingService
from src.services.camera_service import CameraService
from src.services.vehicle_service import VehicleService
from src.services.analytics_service import AnalyticsService

security = HTTPBearer()

# 1. Сессия БД
async def get_session() -> AsyncSession:
    async for session in db_helper.session_getter():
        yield session

SessionDep = Annotated[AsyncSession, Depends(get_session)]


# DAO
def get_spots_dao():
    return SpotDAO()

def get_parking_dao():
    return ParkingDAO()

def get_booking_dao():
    return BookingDAO()

def get_camera_dao():
    return CameraDAO()

def get_vehicle_dao():
    return VehicleDAO()

def get_tracking_dao():
    return TrackingDAO()






# 2. Сервисы — один экземпляр на запрос
def get_spot_service(
    spot_dao: SpotDAO = Depends(get_spots_dao),
    parking_dao: ParkingDAO = Depends(get_parking_dao),
) -> SpotService:
    return SpotService(
        spot_dao=spot_dao,
        parking_dao=parking_dao
    )

def get_parking_service(
        parking_dao: ParkingDAO = Depends(get_parking_dao)
) -> ParkingService:
    return ParkingService(parking_dao=parking_dao)

def get_camera_service(
        camera_dao: CameraDAO = Depends(get_camera_dao),
        parking_dao: ParkingDAO = Depends(get_parking_dao)
) -> CameraService:
    return CameraService(
        camera_dao=camera_dao,
        parking_dao=parking_dao
    )

def get_vehicle_service(
        vehicle_dao: VehicleDAO = Depends(get_vehicle_dao),
        tracking_dao: TrackingDAO = Depends(get_tracking_dao),
) -> VehicleService:
    return VehicleService(
        vehicle_dao=vehicle_dao,
        tracking_dao=tracking_dao,
    )

def get_analytics_service(session: SessionDep) -> AnalyticsService:
    return AnalyticsService(session)

async def get_booking_service(
        booking_dao: BookingDAO = Depends(get_booking_dao),
        spot_dao: SpotDAO = Depends(get_spot_service),
        parking_dao: ParkingDAO = Depends(get_parking_dao),
) -> BookingService:
    return BookingService(
        booking_dao=booking_dao,
        spot_dao=spot_dao,
        parking_dao=parking_dao
    )


async def get_current_user_id(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        auth_client: AuthServiceClient = Depends()
) -> int:
    """
    Получение ID текущего пользователя из Auth Service
    """
    token = credentials.credentials

    # Получаем данные пользователя через эндпоинт /users/me
    user_data = await auth_client.get_current_user(token)

    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )

    return user_data["id"]


# 3. Annotated-алиасы — используются как типы в роутерах
SpotServiceDep    = Annotated[SpotService,    Depends(get_spot_service)]
ParkingServiceDep = Annotated[ParkingService, Depends(get_parking_service)]
CameraServiceDep  = Annotated[CameraService,  Depends(get_camera_service)]
VehicleServiceDep = Annotated[VehicleService, Depends(get_vehicle_service)]
AnalyticsServiceDep = Annotated[AnalyticsService, Depends(get_analytics_service)]
BookingServiceDep = Annotated[BookingService, Depends(get_booking_service)]

# DAO
BookingDaoDep = Annotated[BookingDAO,Depends(get_booking_dao)]
SpotDaoDep = Annotated[SpotDAO, Depends(get_spots_dao)]
ParkingDaoDep = Annotated[ParkingDAO, Depends(get_parking_dao)]
VehicleDaoDep = Annotated[VehicleDAO, Depends(get_vehicle_dao)]
CameraDaoDep = Annotated[CameraDAO, Depends(get_camera_dao)]
TrackingDaoDep = Annotated[TrackingDAO, Depends(get_tracking_dao)]
