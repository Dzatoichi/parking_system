"""
Service-слой CV Processing.
"""

from fastapi import HTTPException, status

from src.repositories.cv_job_repository import CVJobRepository
from src.schemas import CVJobCreate, CVJobRead


class CVJobService:
    """Бизнес-логика управления CV задачами."""

    def __init__(self, repository: CVJobRepository) -> None:
        self._repository = repository

    async def create_job(self, payload: CVJobCreate) -> CVJobRead:
        """Запускает новую задачу обработки потока."""
        created = await self._repository.create(payload.model_dump())
        return self._to_read(created)

    async def get_job(self, job_id: str) -> CVJobRead:
        """Возвращает текущее состояние задачи."""
        job = await self._repository.get_by_id(job_id)
        if job is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="CV job not found",
            )
        return self._to_read(job)

    async def stop_job(self, job_id: str) -> CVJobRead:
        """Останавливает задачу."""
        updated = await self._repository.update_status(
            job_id=job_id,
            status="stopped",
            details={"message": "Job stopped by request"},
        )
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="CV job not found",
            )
        return self._to_read(updated)

    @staticmethod
    def _to_read(job: dict) -> CVJobRead:
        """Маппинг внутренней модели в API-DTO."""
        return CVJobRead(
            job_id=job["job_id"],
            status=job["status"],
            accepted_at=job["accepted_at"],
            details=job["details"],
        )
