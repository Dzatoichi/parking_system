"""
src/utils/dependencies.py

Единое место для всех FastAPI-зависимостей проекта.
Правило: роутеры импортируют только отсюда — никаких локальных Depends.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.base import db_helper
from src.services.spots_service import SpotService
from src.services.parking_service import ParkingService
from src.services.camera_service import CameraService
from src.services.vehicle_service import VehicleService


# 1. Сессия БД
async def get_session() -> AsyncSession:
    async for session in db_helper.session_getter():
        yield session

SessionDep = Annotated[AsyncSession, Depends(get_session)]


# 2. Сервисы — один экземпляр на запрос
def get_spot_service(session: SessionDep) -> SpotService:
    return SpotService(session)

def get_parking_service(session: SessionDep) -> ParkingService:
    return ParkingService(session)

def get_camera_service(session: SessionDep) -> CameraService:
    return CameraService(session)

def get_vehicle_service(session: SessionDep) -> VehicleService:
    return VehicleService(session)


# 3. Annotated-алиасы — используются как типы в роутерах
SpotServiceDep    = Annotated[SpotService,    Depends(get_spot_service)]
ParkingServiceDep = Annotated[ParkingService, Depends(get_parking_service)]
CameraServiceDep  = Annotated[CameraService,  Depends(get_camera_service)]
VehicleServiceDep = Annotated[VehicleService, Depends(get_vehicle_service)]