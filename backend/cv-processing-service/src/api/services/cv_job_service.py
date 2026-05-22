from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status

from src.api.brokers.cv_event_broker import CVEventBroker
from src.api.clients.parking_management_client import ParkingManagementClient
from src.api.repositories.cv_job_repository import CVJobRepository
from src.api.schemas import CVJobCreate, CVJobRead
from src.parking_monitor.core.frame_monitor import FrameParkingMonitor


class CVJobService:
    def __init__(
        self,
        repository: CVJobRepository,
        parking_client: ParkingManagementClient,
        event_broker: CVEventBroker,
        monitor: FrameParkingMonitor,
    ) -> None:
        self._repository = repository
        self._parking_client = parking_client
        self._event_broker = event_broker
        self._monitor = monitor

    async def create_job(self, payload: CVJobCreate) -> CVJobRead:
        created = await self._repository.create(payload.model_dump())
        try:
            camera_id = int(payload.camera_id)
            config = await self._parking_client.get_monitoring_config(camera_id)
            state = self._monitor.create_state(created["job_id"], config, payload.options)
            updated = await self._repository.update_status(
                created["job_id"],
                "running",
                {
                    "message": "Parking monitor initialized",
                    "camera_id": state.camera_id,
                    "parking_id": state.parking_id,
                    "monitored_spots": len(state.spots),
                    "debounce_frames": state.debounce_frames,
                },
            )
            return self._to_read(updated)
        except Exception as exc:
            updated = await self._repository.update_status(
                created["job_id"],
                "failed",
                {"message": f"Failed to initialize parking monitor: {exc}"},
            )
            return self._to_read(updated)

    async def get_job(self, job_id: str) -> CVJobRead:
        job = await self._repository.get_by_id(job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV job not found")
        return self._to_read(job)

    async def stop_job(self, job_id: str) -> CVJobRead:
        self._monitor.stop_state(job_id)
        updated = await self._repository.update_status(
            job_id=job_id,
            status="stopped",
            details={"message": "Job stopped by request"},
        )
        if updated is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV job not found")
        return self._to_read(updated)

    async def process_frame(self, job_id: str, frame_bytes: bytes, test_detections: list[dict] | None = None) -> dict:
        job = await self._repository.get_by_id(job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="CV job not found")
        if job["status"] not in {"running", "queued"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"CV job is {job['status']}")

        try:
            events = self._monitor.process_jpeg(job_id, frame_bytes, test_detections=test_detections)
            for event in events:
                await self._event_broker.publish(self._routing_key(event["event_type"]), event)
            await self._repository.update_status(
                job_id,
                "running",
                {
                    "message": "Frame processed",
                    "events_published": len(events),
                    "last_event_types": [event["event_type"] for event in events[-5:]],
                },
            )
            return {"ok": True, "events_published": len(events), "events": events}
        except Exception as exc:
            error_event = self._build_error_event(job, str(exc))
            await self._event_broker.publish("cv.error", error_event)
            await self._repository.update_status(job_id, "failed", {"message": str(exc)})
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    @staticmethod
    def _routing_key(event_type: str) -> str:
        return {
            "spot.occupied_confirmed": "cv.spot.occupied",
            "spot.free_confirmed": "cv.spot.free",
            "vehicle.detected": "cv.vehicle.detected",
            "vehicle.track_started": "cv.vehicle.detected",
            "vehicle.left_camera": "cv.vehicle.left_camera",
            "cv.device_unavailable": "cv.error",
            "cv.processing_error": "cv.error",
        }.get(event_type, "cv.event")

    @staticmethod
    def _build_error_event(job: dict, message: str) -> dict:
        camera_id = str(job.get("camera_id", ""))
        return {
            "event_id": str(uuid4()),
            "event_type": "cv.processing_error",
            "parking_id": None,
            "camera_id": int(camera_id) if camera_id.isdigit() else None,
            "spot_id": None,
            "cv_track_id": None,
            "vehicle_id": None,
            "plate_number": None,
            "bbox": None,
            "confidence": None,
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "metadata": {"job_id": job["job_id"], "message": message},
        }

    @staticmethod
    def _to_read(job: dict) -> CVJobRead:
        return CVJobRead(
            job_id=job["job_id"],
            status=job["status"],
            accepted_at=job["accepted_at"],
            details=job["details"],
        )
