from fastapi import APIRouter, status

from src.schemas import CameraCreate, CameraUpdate, CameraRead, CameraNetworkRead
from src.utils.dependencies import CameraServiceDep

cameras_router = APIRouter(prefix="/cameras", tags=["cameras"])


@cameras_router.get("/{parking_id}", response_model=CameraNetworkRead)
async def get_cameras(
    parking_id: int,
    service: CameraServiceDep,
) -> CameraNetworkRead:
    return await service.get_cameras_by_parking(parking_id)


@cameras_router.get("/detail/{camera_id}", response_model=CameraRead)
async def get_camera(
    camera_id: int,
    service: CameraServiceDep,
) -> CameraRead:
    return await service.get_camera(camera_id)


@cameras_router.post("/{parking_id}", response_model=CameraRead, status_code=status.HTTP_201_CREATED)
async def create_camera(
    parking_id: int,
    body: CameraCreate,
    service: CameraServiceDep,
) -> CameraRead:
    return await service.create_camera(parking_id, body)


@cameras_router.patch("/{camera_id}", response_model=CameraRead)
async def update_camera(
    camera_id: int,
    body: CameraUpdate,
    service: CameraServiceDep,
) -> CameraRead:
    return await service.update_camera(camera_id, body)


@cameras_router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_camera(
    camera_id: int,
    service: CameraServiceDep,
) -> None:
    await service.delete_camera(camera_id)