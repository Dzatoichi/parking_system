from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.database.base import db_helper
from src.models.cameras import Cameras
from src.models.cv_geometry import CameraCalibration, ParkingContainer, SegmentsConfig
from src.models.spots import Spot

internal_cv_router = APIRouter(prefix="/internal/cv", tags=["internal-cv"])


@internal_cv_router.get("/cameras/{camera_id}/monitoring-config")
async def get_camera_monitoring_config(camera_id: int) -> dict:
    async with db_helper.async_session_maker() as session:
        camera = await session.get(Cameras, camera_id)
        if camera is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Camera not found")

        spot_ids = list(camera.monitored_spot_ids or [])
        spots = []
        if spot_ids:
            rows = await session.execute(select(Spot).where(Spot.id.in_(spot_ids)).order_by(Spot.id))
            spots = rows.scalars().all()

        containers_result = await session.execute(
            select(ParkingContainer).where(ParkingContainer.camera_id == camera_id).order_by(ParkingContainer.id)
        )
        containers = list(containers_result.scalars().all())

        calibrations_result = await session.execute(
            select(CameraCalibration).join(ParkingContainer).where(ParkingContainer.camera_id == camera_id)
        )
        calibrations = list(calibrations_result.scalars().all())

        segments = None
        if camera.segments_config_id is not None:
            segments = await session.get(SegmentsConfig, camera.segments_config_id)

        return {
            "camera": {
                "id": camera.id,
                "parking_id": camera.parking_id,
                "rtsp_url": camera.rtsp_url,
                "monitored_spot_ids": spot_ids,
                "segments_config_id": camera.segments_config_id,
            },
            "segments_config": {
                "id": segments.id,
                "horizontal_segments": segments.horizontal_segments,
                "vertical_segments": segments.vertical_segments,
                "name": segments.name,
            }
            if segments
            else None,
            "spots": [
                {
                    "id": spot.id,
                    "spot_number": spot.spot_number,
                    "spot_type": spot.spot_type.value,
                    "spot_status": spot.spot_status.value,
                    "spot_coordinates": spot.spot_coordinates,
                    "parking_id": spot.parking_id,
                }
                for spot in spots
            ],
            "parking_containers": [
                {
                    "id": container.id,
                    "camera_id": container.camera_id,
                    "spot_id": container.spot_id,
                    "name": container.name,
                    "length": container.length,
                    "width": container.width,
                    "height": container.height,
                    "ground_points": container.ground_points,
                    "upper_points": container.upper_points,
                    "image_points": container.image_points,
                    "is_base": container.is_base,
                }
                for container in containers
            ],
            "camera_calibrations": [
                {
                    "id": calibration.id,
                    "container_id": calibration.container_id,
                    "camera_matrix": calibration.camera_matrix,
                    "dist_coeffs": calibration.dist_coeffs,
                    "image_shape": calibration.image_shape,
                    "rvec": calibration.rvec,
                    "tvec": calibration.tvec,
                    "homography": calibration.homography,
                }
                for calibration in calibrations
            ],
        }
