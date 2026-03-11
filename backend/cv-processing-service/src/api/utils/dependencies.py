"""
Единая точка FastAPI-зависимостей для CV Processing.
"""

from typing import Annotated

from fastapi import Depends

from src.api.repositories.cv_job_repository import CVJobRepository
from src.api.services.cv_job_service import CVJobService

_cv_job_repository = CVJobRepository()


def get_cv_job_service() -> CVJobService:
    """Возвращает service-экземпляр для текущего запроса."""
    return CVJobService(repository=_cv_job_repository)


# Тип-алиас для роутеров.
CVJobServiceDep = Annotated[CVJobService, Depends(get_cv_job_service)]
