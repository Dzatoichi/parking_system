import threading
import json
from pathlib import Path
from typing import Any

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

    def create_markup_scene(self, camera_id: int, containers: list[dict[str, Any]]) -> dict[str, Any]:
        with self._lock:
            if self._monitor is not None and self._monitor.is_running:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Monitoring is active. Stop monitoring before markup.",
                )
            self._mode = "markup"
            return {
                "mode": self._mode,
                "camera_id": camera_id,
                "containers": containers,
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
                        keep_ids: list[int] = []
                        for container in containers:
                            container_id = container.get("id")
                            values = (
                                camera_id,
                                container.get("spot_id"),
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
                                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Container not found")
                            saved_id = int(row[0])
                            keep_ids.append(saved_id)
                            saved.append({**container, "id": saved_id, "camera_id": camera_id})

                        if replace_existing:
                            if keep_ids:
                                cursor.execute(
                                    "DELETE FROM parking_containers WHERE camera_id = %s AND id <> ALL(%s)",
                                    (camera_id, keep_ids),
                                )
                            else:
                                cursor.execute("DELETE FROM parking_containers WHERE camera_id = %s", (camera_id,))

            self._mode = "idle"
            return {
                "mode": self._mode,
                "camera_id": camera_id,
                "saved": saved,
                "count": len(saved),
            }

    def status(self) -> dict[str, Any]:
        monitor = self._monitor
        monitor_status = monitor.get_status() if monitor is not None else None
        return {
            "mode": self._mode,
            "running": bool(monitor and monitor.is_running),
            "monitor": monitor_status,
        }

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
