"""
HTTP-роутер для операций с CV задачами.
"""

from fastapi import APIRouter, status

from src.schemas import CVJobCreate, CVJobRead
from src.utils.dependencies import CVJobServiceDep

cv_job_router = APIRouter(prefix="/v1/jobs", tags=["cv-jobs"])


@cv_job_router.post("", response_model=CVJobRead, status_code=status.HTTP_201_CREATED)
async def create_job(
    body: CVJobCreate,
    service: CVJobServiceDep,
) -> CVJobRead:
    """Создает новую CV задачу."""
    return await service.create_job(body)


@cv_job_router.get("/{job_id}", response_model=CVJobRead)
async def get_job(
    job_id: str,
    service: CVJobServiceDep,
) -> CVJobRead:
    """Возвращает статус CV задачи."""
    return await service.get_job(job_id)


@cv_job_router.post("/{job_id}/stop", response_model=CVJobRead)
async def stop_job(
    job_id: str,
    service: CVJobServiceDep,
) -> CVJobRead:
    """Останавливает CV задачу."""
    return await service.stop_job(job_id)
