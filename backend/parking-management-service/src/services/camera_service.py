from fastapi import HTTPException, status

from src.dao.camera_dao import CameraDAO
from src.dao.parking_dao import ParkingDAO
from src.models.cameras import Cameras
from src.models.status.camera_status import CameraStatus
from src.schemas import (
    CameraCreate,
    CameraUpdate,
    CameraRead,
    CameraNetworkRead,
)


class CameraService:
    def __init__(self, camera_dao: CameraDAO, parking_dao: ParkingDAO) -> None:
        self._dao = camera_dao
        self._parking_dao = parking_dao


    async def get_camera(self, camera_id: int) -> CameraRead:
        camera = await self._dao.get_by_id(camera_id)
        if camera is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Камера с id={camera_id} не найдена",
            )
        return self._to_read(camera)

    async def get_cameras_by_parking(self, parking_id: int) -> CameraNetworkRead:
        cameras, _ = await self._dao.get_by_parking(parking_id)
        return CameraNetworkRead(
            parking_id=parking_id,
            cameras=[self._to_read(c) for c in cameras],
            total=len(cameras),
        )


    async def create_camera(self, parking_id: int, data: CameraCreate) -> CameraRead:
        # Парковка должна существовать
        parking = await self._parking_dao.get_by_id(parking_id)
        if parking is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Парковка с id={parking_id} не найдена",
            )

        # RTSP-URL должен быть уникальным
        existing = await self._dao.get_by_rtsp(data.rtsp_url)
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Камера с URL '{data.rtsp_url}' уже существует",
            )

        camera = Cameras(
            rtsp_url=data.rtsp_url,
            parking_id=parking_id,
            position_x=data.position_x,
            position_y=data.position_y,
            status=CameraStatus.ACTIVE,
        )
        camera_dict = {
            "rtsp_url": data.rtsp_url,
            "parking_id": parking_id,
            "position_x": data.position_x,
            "position_y": data.position_y,
            "status": CameraStatus.ACTIVE,
            "is_calibrated": data.is_calibrated,
            "monitored_spot_ids": data.monitored_spot_ids,
        }
        camera = await self._dao.create(camera_dict)
        return self._to_read(camera)

    async def update_camera(self, camera_id: int, data: CameraUpdate) -> CameraRead:
        existing = await self._dao.get_by_id(camera_id)
        if existing is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Камера с id={camera_id} не найдена",
            )

        values = data.model_dump(exclude_none=True)
        if not values:
            return self._to_read(existing)

        # Проверяем уникальность нового rtsp_url если он меняется
        if "rtsp_url" in values:
            duplicate = await self._dao.get_by_rtsp(values["rtsp_url"])
            if duplicate is not None and duplicate.id != camera_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Камера с URL '{values['rtsp_url']}' уже существует",
                )

        updated = await self._dao.update(camera_id, **values)
        return self._to_read(updated)

    async def delete_camera(self, camera_id: int) -> None:
        camera = await self._dao.get_by_id(camera_id)
        if camera is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Камера с id={camera_id} не найдена",
            )
        await self._dao.delete(camera_id)


    @staticmethod
    def _to_read(camera: Cameras) -> CameraRead:
        return CameraRead(
            id=camera.id,
            rtsp_url=camera.rtsp_url,
            status=camera.status,
            position_x=camera.position_x,
            position_y=camera.position_y,
            is_calibrated=bool(getattr(camera, "is_calibrated", False) or False),
            parking_id=camera.parking_id,
            monitored_spot_ids=getattr(camera, "monitored_spot_ids", []) or [],
        )
