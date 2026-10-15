"""PostgreSQL persistence for parking journeys; embeddings are JSONB until pgvector is available."""
from __future__ import annotations

import json
import logging
from typing import Any, Iterable

import numpy as np
import psycopg2
from psycopg2.extras import Json

from Config import Config

logger = logging.getLogger(__name__)


class ParkingRepository:
    """Small synchronous repository using PostgreSQL wire protocol (no pgvector required)."""

    def __init__(self, params: dict | None = None):
        self.params = dict(params or Config.DB_PARAMS)
        self.connection = None

    def connect(self) -> None:
        if self.connection is not None and not self.connection.closed:
            return
        self.connection = psycopg2.connect(**self.params)
        self.connection.autocommit = False
        self.initialize_schema()

    def close(self) -> None:
        if self.connection is not None and not self.connection.closed:
            self.connection.close()

    def _run(self, sql: str, params: tuple = (), *, fetch: bool = False):
        if self.connection is None or self.connection.closed:
            self.connect()
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql, params)
                result = cursor.fetchone() if fetch else None
            self.connection.commit()
            return result
        except Exception:
            self.connection.rollback()
            logger.exception("Database operation failed")
            raise

    def initialize_schema(self) -> None:
        statements = [
            """
            CREATE TABLE IF NOT EXISTS parking_vehicle (
                global_id BIGSERIAL PRIMARY KEY,
                plate_text TEXT,
                plate_confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
                scan_camera_id INTEGER NOT NULL DEFAULT 1,
                scan_track_id BIGINT,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS parking_plate_read (
                id BIGSERIAL PRIMARY KEY,
                global_id BIGINT NOT NULL REFERENCES parking_vehicle(global_id),
                camera_id INTEGER NOT NULL,
                local_track_id BIGINT NOT NULL,
                frame_id BIGINT NOT NULL,
                plate_text TEXT NOT NULL,
                ocr_confidence DOUBLE PRECISION NOT NULL,
                plate_confidence DOUBLE PRECISION NOT NULL DEFAULT 0,
                subtype TEXT,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS parking_embedding (
                id BIGSERIAL PRIMARY KEY,
                global_id BIGINT NOT NULL REFERENCES parking_vehicle(global_id),
                camera_id INTEGER NOT NULL,
                local_track_id BIGINT NOT NULL,
                frame_id BIGINT NOT NULL,
                embedding JSONB NOT NULL,
                mirrored BOOLEAN NOT NULL DEFAULT FALSE,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS parking_track_event (
                id BIGSERIAL PRIMARY KEY,
                camera_id INTEGER NOT NULL,
                local_track_id BIGINT NOT NULL,
                frame_id BIGINT NOT NULL,
                global_id BIGINT REFERENCES parking_vehicle(global_id),
                event_type TEXT NOT NULL,
                source_camera_id INTEGER,
                target_camera_id INTEGER,
                movement_state TEXT,
                bbox JSONB,
                score DOUBLE PRECISION,
                details JSONB NOT NULL DEFAULT '{}'::jsonb,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            "CREATE INDEX IF NOT EXISTS ix_parking_plate_global ON parking_plate_read(global_id, created_at)",
            "CREATE INDEX IF NOT EXISTS ix_parking_embedding_global ON parking_embedding(global_id, camera_id)",
            "CREATE INDEX IF NOT EXISTS ix_parking_event_track ON parking_track_event(camera_id, local_track_id, frame_id)",
        ]
        try:
            with self.connection.cursor() as cursor:
                for statement in statements:
                    cursor.execute(statement)
            self.connection.commit()
        except Exception:
            self.connection.rollback()
            logger.exception("Failed to initialize parking database schema")
            raise

    def create_vehicle(self, camera_id: int, local_track_id: int, frame_id: int) -> int:
        row = self._run(
            """INSERT INTO parking_vehicle(scan_camera_id, scan_track_id)
               VALUES (%s, %s) RETURNING global_id""",
            (int(camera_id), int(local_track_id)), fetch=True,
        )
        global_id = int(row[0])
        self.record_event(
            camera_id, local_track_id, frame_id, "vehicle_registered",
            global_id=global_id, details={"registration_source": "scan_zone"},
        )
        return global_id

    def update_plate(
        self, global_id: int, camera_id: int, local_track_id: int, frame_id: int,
        text: str, ocr_confidence: float, plate_confidence: float = 0.0,
        subtype: str = "",
    ) -> None:
        text = str(text or "").strip().upper()
        if not text:
            return
        self._run(
            """INSERT INTO parking_plate_read
               (global_id, camera_id, local_track_id, frame_id, plate_text,
                ocr_confidence, plate_confidence, subtype)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (int(global_id), int(camera_id), int(local_track_id), int(frame_id), text,
             float(ocr_confidence), float(plate_confidence), str(subtype or "")),
        )
        self._run(
            """UPDATE parking_vehicle
               SET plate_text=%s, plate_confidence=%s, updated_at=NOW()
               WHERE global_id=%s AND (%s >= plate_confidence OR plate_text IS NULL)""",
            (text, float(ocr_confidence), int(global_id), float(ocr_confidence)),
        )

    def save_embedding(
        self, global_id: int, camera_id: int, local_track_id: int, frame_id: int,
        vector: Iterable[float], mirrored: bool = False,
    ) -> None:
        values = np.asarray(vector, dtype=np.float32).reshape(-1)
        if values.size == 0 or not np.isfinite(values).all():
            return
        norm = float(np.linalg.norm(values))
        if norm <= 1e-12:
            return
        normalized = (values / norm).astype(float).tolist()
        self._run(
            """INSERT INTO parking_embedding
               (global_id,camera_id,local_track_id,frame_id,embedding,mirrored)
               VALUES (%s,%s,%s,%s,%s,%s)""",
            (int(global_id), int(camera_id), int(local_track_id), int(frame_id),
             Json(normalized), bool(mirrored)),
        )

    def load_embeddings(self, global_id: int) -> list[dict[str, Any]]:
        if self.connection is None or self.connection.closed:
            self.connect()
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(
                    """SELECT camera_id, local_track_id, frame_id, embedding, mirrored
                       FROM parking_embedding WHERE global_id=%s ORDER BY id""",
                    (int(global_id),),
                )
                rows = cursor.fetchall()
            self.connection.commit()
            return [
                {"camera_id": int(row[0]), "local_track_id": int(row[1]),
                 "frame_id": int(row[2]), "embedding": row[3],
                 "mirrored": bool(row[4])}
                for row in rows
            ]
        except Exception:
            self.connection.rollback()
            raise

    def record_event(
        self, camera_id: int, local_track_id: int, frame_id: int, event_type: str,
        *, global_id: int | None = None, source_camera_id: int | None = None,
        target_camera_id: int | None = None, movement_state: str | None = None,
        bbox: Iterable[float] | None = None, score: float | None = None,
        details: dict | None = None,
    ) -> None:
        self._run(
            """INSERT INTO parking_track_event
               (camera_id,local_track_id,frame_id,global_id,event_type,source_camera_id,
                target_camera_id,movement_state,bbox,score,details)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (int(camera_id), int(local_track_id), int(frame_id),
             int(global_id) if global_id is not None else None, str(event_type),
             int(source_camera_id) if source_camera_id is not None else None,
             int(target_camera_id) if target_camera_id is not None else None,
             movement_state, Json(list(map(float, bbox))) if bbox is not None else None,
             float(score) if score is not None else None, Json(details or {})),
        )

    def update_vehicle_status(self, global_id: int, status: str) -> None:
        self._run(
            "UPDATE parking_vehicle SET status=%s, updated_at=NOW() WHERE global_id=%s",
            (str(status), int(global_id)),
        )
