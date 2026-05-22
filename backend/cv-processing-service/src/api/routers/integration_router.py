from fastapi import APIRouter

cv_router = APIRouter(prefix="/cv-events", tags=["cv-integration"])


@cv_router.get("/contract")
async def cv_events_contract() -> dict:
    return {
        "exchange": "parking.cv",
        "routing_keys": [
            "cv.spot.occupied",
            "cv.spot.free",
            "cv.vehicle.detected",
            "cv.vehicle.left_camera",
            "cv.error",
        ],
        "payload_fields": [
            "event_id",
            "event_type",
            "parking_id",
            "camera_id",
            "spot_id",
            "cv_track_id",
            "vehicle_id",
            "plate_number",
            "bbox",
            "confidence",
            "timestamp",
            "metadata",
        ],
    }
