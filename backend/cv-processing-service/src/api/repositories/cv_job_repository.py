"""
Repository-слой CV задач.

Сейчас хранение in-memory, чтобы интерфейс слоя уже был стабильным.
"""

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


class CVJobRepository:
    """CRUD-операции для состояния CV задач."""

    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}

    async def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Создает новую задачу и сохраняет ее в хранилище."""
        job_id = str(uuid4())
        accepted_at = datetime.now(timezone.utc)

        job = {
            "job_id": job_id,
            "camera_id": payload["camera_id"],
            "stream_url": payload["stream_url"],
            "correlation_id": payload.get("correlation_id"),
            "options": payload.get("options", {}),
            "status": "queued",
            "accepted_at": accepted_at,
            "details": {"message": "Job accepted by cv-processing-service"},
        }
        self._jobs[job_id] = job
        return deepcopy(job)

    async def get_by_id(self, job_id: str) -> dict[str, Any] | None:
        """Возвращает задачу по id или None."""
        job = self._jobs.get(job_id)
        if job is None:
            return None
        return deepcopy(job)

    async def update_status(self, job_id: str, status: str, details: dict[str, Any]) -> dict[str, Any] | None:
        """Обновляет статус задачи."""
        job = self._jobs.get(job_id)
        if job is None:
            return None

        job["status"] = status
        job["details"] = details
        return deepcopy(job)
