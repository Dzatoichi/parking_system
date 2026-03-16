"""
Repository-слой ingest задач.

Сейчас хранение in-memory, чтобы интерфейс слоя уже был стабильным.
"""

from copy import deepcopy
from datetime import datetime
from typing import Any
from uuid import uuid4


class IngestRepository:
    """CRUD-операции для ingest-задач."""

    def __init__(self) -> None:
        self._ingests: dict[str, dict[str, Any]] = {}

    async def create(self, cv_job: dict[str, Any]) -> dict[str, Any]:
        """Создает ingest запись на основе созданной CV задачи."""
        ingest_id = str(uuid4())
        ingest = {
            "ingest_id": ingest_id,
            "cv_job_id": cv_job["job_id"],
            "status": cv_job["status"],
            "accepted_at": self._parse_datetime(cv_job["accepted_at"]),
            "details": cv_job.get("details", {}),
        }
        self._ingests[ingest_id] = ingest
        return deepcopy(ingest)

    async def get_by_id(self, ingest_id: str) -> dict[str, Any] | None:
        """Возвращает ingest по id или None."""
        ingest = self._ingests.get(ingest_id)
        if ingest is None:
            return None
        return deepcopy(ingest)

    async def update_status(self, ingest_id: str, cv_job: dict[str, Any]) -> dict[str, Any] | None:
        """Синхронизирует статус ingest с состоянием CV задачи."""
        ingest = self._ingests.get(ingest_id)
        if ingest is None:
            return None

        ingest["status"] = cv_job["status"]
        ingest["details"] = cv_job.get("details", {})
        self._ingests[ingest_id] = ingest
        return deepcopy(ingest)

    @staticmethod
    def _parse_datetime(value: Any) -> datetime:
        """Нормализует дату из CV API в datetime."""
        if isinstance(value, datetime):
            return value
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
