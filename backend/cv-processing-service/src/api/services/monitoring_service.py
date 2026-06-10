import threading
import json
from pathlib import Path
from typing import Any

import cv2
import httpx
import numpy as np
from fastapi import HTTPException, status

from src.api.settings.config import settings


class MonitoringService:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._pool: Any | None = None
        self._repo: Any | None = None
        self._monitor: Any | None = None
        self._mode = "idle"

    def start_monitoring(self) -> dict[str, Any]:
        with self._lock:
            if self._mode == "markup":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Markup mode is active. Save or cancel markup before starting monitoring.",
                )
            if self._monitor is not None and self._monitor.is_running:
                return self.status()

            from src.parking_monitor.core.parking_monitor import ParkingMonitor

            try:
                repo = self._get_repo()
                monitor = ParkingMonitor(repo)
                monitor.initialize_from_db()
                self._patch_model_paths(monitor)
                monitor.start()
                self._monitor = monitor
                self._mode = "monitoring"
                return self.status()
            except HTTPException:
                raise
            except Exception as exc:
                self._monitor = None
                self._mode = "idle"
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to start parking monitor: {exc}",
                ) from exc

    def stop_monitoring(self) -> dict[str, Any]:
        with self._lock:
            if self._monitor is not None:
                self._monitor.stop()
                self._monitor = None
            if self._mode == "monitoring":
                self._mode = "idle"
            return self.status()

    def begin_markup(self) -> dict[str, Any]:
        with self._lock:
            if self._monitor is not None and self._monitor.is_running:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Monitoring is active. Stop monitoring before markup.",
                )
            self._mode = "markup"
            return self.status()

    def finish_markup(self) -> dict[str, Any]:
        with self._lock:
            if self._mode == "markup":
                self._mode = "idle"
            return self.status()

    def get_camera_frame(self, camera_id: int) -> bytes:
        config = self._get_camera_config(camera_id)
        camera_config = config.get("camera") if isinstance(config.get("camera"), dict) else {}
        source = str(
            camera_config.get("rtsp_url")
            or camera_config.get("video_path")
            or config.get("rtsp_url")
            or config.get("video_path")
            or ""
        )
        if not source:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Camera {camera_id} source is empty",
            )

        capture = cv2.VideoCapture(source)
        try:
            ok, frame = capture.read()
        finally:
            capture.release()

        if not ok or frame is None:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to read camera frame from {source}",
            )

        encoded, buffer = cv2.imencode(".jpg", frame)
        if not encoded:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to encode camera frame")
        return buffer.tobytes()

    @staticmethod
    def _get_camera_config(camera_id: int) -> dict[str, Any]:
        errors: list[str] = []
        with httpx.Client(timeout=10.0) as client:
            for path in (
                f"/internal/cv/cameras/{camera_id}/monitoring-config",
                f"/cameras/detail/{camera_id}",
            ):
                try:
                    response = client.get(f"{settings.PARKING_MANAGEMENT_URL}{path}")
                    if response.status_code == status.HTTP_404_NOT_FOUND:
                        errors.append(f"{path}: 404")
                        continue
                    response.raise_for_status()
                    data = response.json()
                    if "camera" in data:
                        return data
                    return {"camera": data}
                except Exception as exc:
                    errors.append(f"{path}: {exc}")

        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera {camera_id} not found or unavailable ({'; '.join(errors)})",
        )

    def create_markup_scene(
        self,
        camera_id: int,
        image_width: int | None,
        image_height: int | None,
        containers: list[dict[str, Any]],
    ) -> dict[str, Any]:
        with self._lock:
            if self._monitor is not None and self._monitor.is_running:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Monitoring is active. Stop monitoring before markup.",
                )
            if image_width is None or image_height is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="image_width and image_height are required to build a 3D markup scene.",
                )

            base_containers = [container for container in containers if container.get("is_base")]
            if len(base_containers) != 1:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Exactly one base container is required to build a 3D markup scene.",
                )
            for container in containers:
                image_points = container.get("image_points")
                if not isinstance(image_points, list) or len(image_points) != 4:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                        detail=f"Container '{container.get('name')}' must have exactly four image_points.",
                    )

            from src.parking_monitor.core.scene3d import Scene3D

            scene = Scene3D(camera_id=camera_id)
            scene.set_camera_from_image((image_height, image_width))

            ordered = [*base_containers, *[container for container in containers if not container.get("is_base")]]
            for container in ordered:
                image_points = np.array(container["image_points"], dtype=np.float32)
                if container.get("is_base"):
                    new_id = scene.create_base_container(
                        image_points=image_points,
                        length=float(container["length"]),
                        width=float(container["width"]),
                        height=float(container["height"]),
                        name=str(container["name"]),
                    )
                else:
                    new_id = scene.create_container(
                        image_points=image_points,
                        length=float(container["length"]),
                        width=float(container["width"]),
                        height=float(container["height"]),
                        name=str(container["name"]),
                    )

                requested_id = container.get("id")
                if requested_id:
                    requested_id = int(requested_id)
                    if requested_id != new_id:
                        scene_container = scene.containers.pop(new_id)
                        scene_container.id = requested_id
                        scene.containers[requested_id] = scene_container
                        if scene.base_container_id == new_id:
                            scene.base_container_id = requested_id
                    scene.next_container_id = max(scene.next_container_id, requested_id + 1)

            input_by_id = {
                int(container["id"]): container
                for container in containers
                if container.get("id") is not None
            }
            input_by_name = {str(container["name"]): container for container in containers}
            response_containers: list[dict[str, Any]] = []
            for container_id, container in scene.containers.items():
                original = input_by_id.get(container_id) or input_by_name.get(container.name) or {}
                response_containers.append(
                    {
                        "id": container.id,
                        "spot_id": original.get("spot_id"),
                        "camera_id": camera_id,
                        "name": container.name,
                        "length": container.length,
                        "width": container.width,
                        "height": container.height,
                        "ground_points": self._array_to_list_2d(container.ground_points),
                        "upper_points": self._array_to_list_2d(container.upper_points),
                        "image_points": self._array_to_list_2d(container.image_points)
                        if container.image_points is not None
                        else None,
                        "is_base": container_id == scene.base_container_id,
                    }
                )

            self._mode = "markup"
            return {
                "mode": self._mode,
                "camera_id": camera_id,
                "containers": response_containers,
            }

    def save_markup(self, camera_id: int, containers: list[dict[str, Any]], replace_existing: bool = False) -> dict[str, Any]:
        with self._lock:
            if self._monitor is not None and self._monitor.is_running:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Monitoring is active. Stop monitoring before saving markup.",
                )

            repo = self._get_repo()
            saved: list[dict[str, Any]] = []
            with repo._get_connection() as conn:
                with repo._transaction(conn):
                    with conn.cursor() as cursor:
                        cursor.execute("SELECT parking_id FROM camera_table WHERE id = %s", (camera_id,))
                        camera_row = cursor.fetchone()
                        if camera_row is None:
                            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Camera {camera_id} not found")
                        parking_id = int(camera_row[0])

                        cursor.execute(
                            "SELECT id, spot_id FROM parking_containers WHERE camera_id = %s",
                            (camera_id,),
                        )
                        existing_container_spots = {
                            int(row[0]): int(row[1]) if row[1] is not None else None
                            for row in cursor.fetchall()
                        }
                        keep_ids: list[int] = []
                        saved_spot_ids: list[int] = []
                        for container in containers:
                            raw_container_id = container.get("id")
                            container_id = int(raw_container_id) if raw_container_id is not None else None
                            if container_id is not None and container_id <= 0:
                                container_id = None
                            spot_id = self._upsert_markup_spot(
                                cursor,
                                parking_id=parking_id,
                                name=str(container["name"]),
                                image_points=container.get("image_points"),
                                spot_id=container.get("spot_id")
                                or (existing_container_spots.get(container_id) if container_id else None),
                            )
                            values = (
                                camera_id,
                                spot_id,
                                container["name"],
                                container["length"],
                                container["width"],
                                container["height"],
                                json.dumps(container["ground_points"]),
                                json.dumps(container["upper_points"]),
                                json.dumps(container["image_points"]) if container.get("image_points") is not None else None,
                                bool(container.get("is_base", False)),
                            )
                            if container_id:
                                cursor.execute(
                                    """
                                    UPDATE parking_containers
                                    SET camera_id = %s,
                                        spot_id = %s,
                                        name = %s,
                                        length = %s,
                                        width = %s,
                                        height = %s,
                                        ground_points = %s,
                                        upper_points = %s,
                                        image_points = %s,
                                        is_base = %s,
                                        updated_at = NOW()
                                    WHERE id = %s
                                    RETURNING id
                                    """,
                                    (*values, container_id),
                                )
                                row = cursor.fetchone()
                                if row is None:
                                    cursor.execute(
                                        """
                                        INSERT INTO parking_containers
                                        (camera_id, spot_id, name, length, width, height, ground_points, upper_points, image_points, is_base)
                                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                        RETURNING id
                                        """,
                                        values,
                                    )
                                    row = cursor.fetchone()
                            else:
                                cursor.execute(
                                    """
                                    INSERT INTO parking_containers
                                    (camera_id, spot_id, name, length, width, height, ground_points, upper_points, image_points, is_base)
                                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                    RETURNING id
                                    """,
                                    values,
                                )
                                row = cursor.fetchone()
                            if row is None:
                                raise RuntimeError("Failed to save parking container")
                            saved_id = int(row[0])
                            keep_ids.append(saved_id)
                            saved_spot_ids.append(spot_id)
                            saved.append({**container, "id": saved_id, "spot_id": spot_id, "camera_id": camera_id})

                            cursor.execute(
                                """
                                INSERT INTO parking_spots_current (spot_id, status, last_updated)
                                VALUES (%s, 'free', NOW())
                                ON CONFLICT (spot_id) DO NOTHING
                                """,
                                (saved_id,),
                            )

                        if replace_existing:
                            removed_spot_ids = [
                                spot_id
                                for container_id, spot_id in existing_container_spots.items()
                                if container_id not in keep_ids and spot_id is not None and spot_id not in saved_spot_ids
                            ]
                            if keep_ids:
                                cursor.execute(
                                    "DELETE FROM parking_containers WHERE camera_id = %s AND id <> ALL(%s)",
                                    (camera_id, keep_ids),
                                )
                            else:
                                cursor.execute("DELETE FROM parking_containers WHERE camera_id = %s", (camera_id,))
                            if removed_spot_ids:
                                cursor.execute("DELETE FROM spots_table WHERE parking_id = %s AND id = ANY(%s)", (parking_id, removed_spot_ids))

                        cursor.execute(
                            "UPDATE camera_table SET monitored_spot_ids = %s, is_calibrated = true WHERE id = %s",
                            (json.dumps(saved_spot_ids), camera_id),
                        )
                        cursor.execute(
                            """
                            UPDATE parkings_table
                            SET total_spots = counts.total_spots,
                                available_spots = counts.available_spots
                            FROM (
                                SELECT
                                    COUNT(*)::int AS total_spots,
                                    COUNT(*) FILTER (WHERE spot_status = 'FREE')::int AS available_spots
                                FROM spots_table
                                WHERE parking_id = %s
                            ) AS counts
                            WHERE parkings_table.id = %s
                            """,
                            (parking_id, parking_id),
                        )

            self._mode = "idle"
            return {
                "mode": self._mode,
                "camera_id": camera_id,
                "saved": saved,
                "count": len(saved),
            }

    def _upsert_markup_spot(
        self,
        cursor: Any,
        *,
        parking_id: int,
        name: str,
        image_points: Any,
        spot_id: Any = None,
    ) -> int:
        coordinates = self._spot_coordinates_from_image_points(image_points)
        normalized_spot_id = int(spot_id) if spot_id is not None else None
        if normalized_spot_id is not None and normalized_spot_id <= 0:
            normalized_spot_id = None

        if normalized_spot_id is not None:
            cursor.execute(
                """
                UPDATE spots_table
                SET spot_number = %s,
                    spot_coordinates = %s,
                    parking_id = %s
                WHERE id = %s
                RETURNING id
                """,
                (name, json.dumps(coordinates), parking_id, normalized_spot_id),
            )
            row = cursor.fetchone()
            if row is not None:
                return int(row[0])

        cursor.execute(
            """
            INSERT INTO spots_table (
                spot_number,
                spot_type,
                spot_status,
                spot_coordinates,
                occupied_since,
                current_vehicle_id,
                parking_id
            )
            VALUES (%s, 'STANDARD', 'FREE', %s, NULL, NULL, %s)
            ON CONFLICT (parking_id, spot_number) DO UPDATE SET
                spot_coordinates = EXCLUDED.spot_coordinates
            RETURNING id
            """,
            (name, json.dumps(coordinates), parking_id),
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError("Failed to save parking spot")
        return int(row[0])

    @staticmethod
    def _spot_coordinates_from_image_points(image_points: Any) -> dict[str, Any]:
        if not isinstance(image_points, list) or len(image_points) < 3:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Each saved container must have at least three image_points to update ParkingMap and CV monitoring.",
            )
        points: list[list[float]] = []
        for point in image_points:
            if not isinstance(point, list | tuple) or len(point) < 2:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Container image_points must be [x, y] pairs.",
                )
            points.append([float(point[0]), float(point[1])])
        return {
            "points": points,
            "center_x": sum(point[0] for point in points) / len(points),
            "center_y": sum(point[1] for point in points) / len(points),
        }

    def status(self) -> dict[str, Any]:
        monitor = self._monitor
        monitor_status = monitor.get_status() if monitor is not None else None
        return {
            "mode": self._mode,
            "running": bool(monitor and monitor.is_running),
            "monitor": monitor_status,
        }

    def get_scenes_snapshot(self) -> dict[str, Any]:
        with self._lock:
            monitor = self._monitor
            if monitor is None:
                repo = self._get_repo()
                cameras = repo.get_all_cameras()
                scenes = {}
                for camera in cameras:
                    if not camera.is_active:
                        continue
                    containers = [container.to_dict() for container in repo.get_camera_containers(camera.id)]
                    scenes[str(camera.id)] = self._serialize_scene(camera.id, containers)
                return {"type": "all_scenes", "data": scenes}

            scenes = {}
            for camera_id, scene in monitor.scenes.items():
                containers = []
                for container in scene.containers.values():
                    item = container.to_dict()
                    state = monitor.spot_manager.spots.get(container.id) if monitor.spot_manager else None
                    status_value = getattr(getattr(state, "status", None), "value", None)
                    item["occupied"] = status_value in {"parking_pending", "parking_confirmed"}
                    parked_since = getattr(state, "confirmed_time", None)
                    item["parked_since"] = parked_since.isoformat() if parked_since else None
                    containers.append(item)
                scene_data = self._serialize_scene(camera_id, containers)
                scene_data["vehicles"] = [
                    {
                        "track_id": car.track_id,
                        "center": self._array_to_list(car.center),
                        "direction": self._array_to_list(car.direction) if car.direction is not None else None,
                        "container_id": car.container_id,
                    }
                    for car in scene.get_current_cars()
                ]
                scenes[str(camera_id)] = scene_data
            return {"type": "all_scenes", "data": scenes}

    @staticmethod
    def _serialize_scene(camera_id: int, containers: list[dict[str, Any]]) -> dict[str, Any]:
        serialized = []
        all_points: list[list[float]] = []
        for container in containers:
            ground_points = container.get("ground_points") or []
            polygon = [[float(point[0]), float(point[2])] for point in ground_points]
            all_points.extend(polygon)
            serialized.append({
                **container,
                "camera_id": camera_id,
                "polygon": polygon,
            })

        if all_points:
            xs = [point[0] for point in all_points]
            zs = [point[1] for point in all_points]
            bbox = [min(xs), min(zs), max(xs), max(zs)]
        else:
            bbox = [0, 0, 10, 10]

        return {
            "camera_id": camera_id,
            "bbox": bbox,
            "containers": serialized,
            "spots": serialized,
            "vehicles": [],
        }

    @staticmethod
    def _array_to_list(value: Any) -> list[float]:
        return [float(item) for item in value]

    @staticmethod
    def _array_to_list_2d(value: Any) -> list[list[float]]:
        return [[float(item) for item in point] for point in value]

    def _get_repo(self) -> Any:
        if self._pool is None:
            try:
                from psycopg2 import pool
            except ModuleNotFoundError as exc:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="psycopg2 is not installed in cv-processing-service. Rebuild the Docker image after dependency changes.",
                ) from exc

            from src.parking_monitor.db.repository import ParkingRepository

            self._pool = pool.SimpleConnectionPool(
                minconn=settings.PARKING_DB_POOL_MIN,
                maxconn=settings.PARKING_DB_POOL_MAX,
                dbname=settings.PARKING_DB_NAME,
                user=settings.PARKING_DB_USER,
                password=settings.PARKING_DB_PASSWORD,
                host=settings.PARKING_DB_HOST,
                port=settings.PARKING_DB_PORT,
            )
            self._repo = ParkingRepository(self._pool)
        if self._repo is None:
            raise RuntimeError("Parking repository was not initialized")
        return self._repo

    @staticmethod
    def _patch_model_paths(monitor: Any) -> None:
        model_path = Path(__file__).resolve().parents[2] / "parking_monitor" / "best.pt"
        for processor in monitor.processors.values():
            processor.model_path = str(model_path)
