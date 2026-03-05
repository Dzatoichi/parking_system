"""
Единая точка FastAPI-зависимостей для Stream Ingest.
"""

from typing import Annotated

from fastapi import Depends

from src.clients.cv_client import CVServiceClient
from src.repositories.ingest_repository import IngestRepository
from src.services.ingest_service import IngestService

_ingest_repository = IngestRepository()
_cv_client = CVServiceClient()


def get_ingest_service() -> IngestService:
    """Возвращает service-экземпляр для текущего запроса."""
    return IngestService(repository=_ingest_repository, cv_client=_cv_client)


# Тип-алиас для роутеров.
IngestServiceDep = Annotated[IngestService, Depends(get_ingest_service)]
