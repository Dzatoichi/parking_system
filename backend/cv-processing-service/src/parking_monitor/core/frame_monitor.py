from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import numpy as np

try:
    import cv2
except Exception:  # pragma: no cover - import depends on runtime image
    cv2 = None

try:
    from ultralytics import YOLO
except Exception:  # pragma: no cover - model is optional for API tests
    YOLO = None

from src.api.settings.config import settings


@dataclass
class Detection:
    cv_track_id: str
    bbox: dict[str, float]
    confidence: float
    center: tuple[float, float]


@dataclass
class SpotRuntime:
    status: str = "unknown"
    occupied_frames: int = 0
    free_frames: int = 0
    last_track_id: str | None = None
    last_bbox: dict[str, float] | None = None
    last_confidence: float | None = None


@dataclass
class JobMonitorState:
    job_id: str
    camera_id: int
    parking_id: int
    spots: list[dict[str, Any]]
    fps: float
    debounce_frames: int
    frame_number: int = 0
    seen_tracks: set[str] = field(default_factory=set)
    spot_state: dict[int, SpotRuntime] = field(default_factory=dict)


class FrameParkingMonitor:
    def __init__(self) -> None:
        self._states: dict[str, JobMonitorState] = {}
        self._model = None

    def create_state(self, job_id: str, config: dict[str, Any], options: dict[str, Any] | None = None) -> JobMonitorState:
        options = options or {}
        camera = config["camera"]
        fps = float(options.get("fps") or settings.CV_DEFAULT_FPS)
        debounce_seconds = float(options.get("debounce_seconds") or settings.CV_OCCUPANCY_DEBOUNCE_SECONDS)
        state = JobMonitorState(
            job_id=job_id,
            camera_id=int(camera["id"]),
            parking_id=int(camera["parking_id"]),
            spots=list(config.get("spots", [])),
            fps=fps,
            debounce_frames=max(1, int(round(fps * debounce_seconds))),
        )
        self._states[job_id] = state
        return state

    def stop_state(self, job_id: str) -> None:
        self._states.pop(job_id, None)

    def get_state(self, job_id: str) -> JobMonitorState | None:
        return self._states.get(job_id)

    def process_jpeg(
        self,
        job_id: str,
        frame_bytes: bytes,
        test_detections: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        state = self._states.get(job_id)
        if state is None:
            raise KeyError(f"CV job monitor state not found: {job_id}")

        state.frame_number += 1
        detections = self._decode_test_detections(test_detections)
        if detections is None:
            detections = self._detect(frame_bytes)

        now = datetime.now(tz=timezone.utc)
        events: list[dict[str, Any]] = []
        occupied_by_spot: dict[int, Detection] = {}

        for detection in detections:
            events.append(self._event(state, "vehicle.detected", timestamp=now, detection=detection))
            if detection.cv_track_id not in state.seen_tracks:
                state.seen_tracks.add(detection.cv_track_id)
                events.append(self._event(state, "vehicle.track_started", timestamp=now, detection=detection))

            spot = self._match_spot(state.spots, detection.center)
            if spot is not None:
                occupied_by_spot[int(spot["id"])] = detection

        for spot in state.spots:
            spot_id = int(spot["id"])
            runtime = state.spot_state.setdefault(spot_id, SpotRuntime())
            detection = occupied_by_spot.get(spot_id)
            if detection is not None:
                runtime.occupied_frames += 1
                runtime.free_frames = 0
                runtime.last_track_id = detection.cv_track_id
                runtime.last_bbox = detection.bbox
                runtime.last_confidence = detection.confidence
                if runtime.status != "occupied" and runtime.occupied_frames >= state.debounce_frames:
                    runtime.status = "occupied"
                    events.append(
                        self._event(
                            state,
                            "spot.occupied_confirmed",
                            timestamp=now,
                            spot_id=spot_id,
                            detection=detection,
                        )
                    )
            else:
                runtime.free_frames += 1
                runtime.occupied_frames = 0
                if runtime.status == "occupied" and runtime.free_frames >= state.debounce_frames:
                    runtime.status = "free"
                    events.append(
                        self._event(
                            state,
                            "spot.free_confirmed",
                            timestamp=now,
                            spot_id=spot_id,
                            cv_track_id=runtime.last_track_id,
                            bbox=runtime.last_bbox,
                            confidence=runtime.last_confidence,
                        )
                    )

        return events

    def _decode_test_detections(self, raw: list[dict[str, Any]] | None) -> list[Detection] | None:
        if raw is None:
            return None

        detections: list[Detection] = []
        for idx, item in enumerate(raw):
            bbox = item.get("bbox") or {}
            if {"x1", "y1", "x2", "y2"}.issubset(bbox):
                center = (float((bbox["x1"] + bbox["x2"]) / 2), float(bbox["y2"]))
            else:
                center_data = item.get("center") or [0, 0]
                center = (float(center_data[0]), float(center_data[1]))
                bbox = {"x1": center[0], "y1": center[1], "x2": center[0], "y2": center[1]}

            detections.append(
                Detection(
                    cv_track_id=str(item.get("cv_track_id") or item.get("track_id") or idx + 1),
                    bbox={k: float(v) for k, v in bbox.items()},
                    confidence=float(item.get("confidence", bbox.get("confidence", 1.0))),
                    center=center,
                )
            )
        return detections

    def _detect(self, frame_bytes: bytes) -> list[Detection]:
        if cv2 is None or YOLO is None:
            return []

        arr = np.frombuffer(frame_bytes, dtype=np.uint8)
        frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if frame is None:
            return []

        if self._model is None:
            self._model = YOLO(settings.YOLO_MODEL_PATH)

        results = self._model.track(frame, classes=[2], verbose=False, conf=0.5, persist=True)
        if not results or results[0].boxes is None:
            return []

        boxes = results[0].boxes
        xyxy = boxes.xyxy.cpu().numpy() if boxes.xyxy is not None else []
        confs = boxes.conf.cpu().numpy() if boxes.conf is not None else []
        ids = boxes.id.cpu().numpy().astype(int) if boxes.id is not None else list(range(1, len(xyxy) + 1))

        detections: list[Detection] = []
        for idx, box in enumerate(xyxy):
            x1, y1, x2, y2 = [float(v) for v in box]
            detections.append(
                Detection(
                    cv_track_id=str(ids[idx]),
                    bbox={
                        "x1": x1,
                        "y1": y1,
                        "x2": x2,
                        "y2": y2,
                        "confidence": float(confs[idx]) if idx < len(confs) else 1.0,
                    },
                    confidence=float(confs[idx]) if idx < len(confs) else 1.0,
                    center=((x1 + x2) / 2, y2),
                )
            )
        return detections

    def _match_spot(self, spots: list[dict[str, Any]], point: tuple[float, float]) -> dict[str, Any] | None:
        for spot in spots:
            coordinates = spot.get("spot_coordinates") or {}
            points = coordinates.get("points") or []
            if self._point_in_polygon(point, points):
                return spot
        return None

    @staticmethod
    def _point_in_polygon(point: tuple[float, float], polygon: list[list[float]]) -> bool:
        if len(polygon) < 3:
            return False
        x, y = point
        inside = False
        j = len(polygon) - 1
        for i in range(len(polygon)):
            xi, yi = polygon[i]
            xj, yj = polygon[j]
            if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi):
                inside = not inside
            j = i
        return inside

    def _event(
        self,
        state: JobMonitorState,
        event_type: str,
        *,
        timestamp: datetime,
        detection: Detection | None = None,
        spot_id: int | None = None,
        cv_track_id: str | None = None,
        bbox: dict[str, float] | None = None,
        confidence: float | None = None,
    ) -> dict[str, Any]:
        return {
            "event_id": str(uuid4()),
            "event_type": event_type,
            "parking_id": state.parking_id,
            "camera_id": state.camera_id,
            "spot_id": spot_id,
            "cv_track_id": detection.cv_track_id if detection else cv_track_id,
            "vehicle_id": None,
            "plate_number": None,
            "bbox": detection.bbox if detection else bbox,
            "confidence": detection.confidence if detection else confidence,
            "timestamp": timestamp.isoformat(),
            "metadata": {
                "job_id": state.job_id,
                "frame_number": state.frame_number,
                "debounce_frames": state.debounce_frames,
            },
        }


def decode_test_detections_header(value: str | None) -> list[dict[str, Any]] | None:
    if not value:
        return None
    decoded = json.loads(value)
    if not isinstance(decoded, list):
        raise ValueError("X-Test-Detections must contain a JSON list")
    return decoded
