"""
HTTP-роутер для stream ingest API.
"""

from fastapi import APIRouter, status

from src.schemas import IngestCreate, IngestRead
from src.utils.dependencies import IngestServiceDep

ingest_router = APIRouter(prefix="/v1/ingest/streams", tags=["ingest"])


@ingest_router.post("", response_model=IngestRead, status_code=status.HTTP_201_CREATED)
async def start_ingest(
    body: IngestCreate,
    service: IngestServiceDep,
) -> IngestRead:
    """Запускает ingest процесс."""
    return await service.start_ingest(body)


@ingest_router.get("/{ingest_id}", response_model=IngestRead)
async def get_ingest(
    ingest_id: str,
    service: IngestServiceDep,
) -> IngestRead:
    """Возвращает текущее состояние ingest."""
    return await service.get_ingest(ingest_id)


@ingest_router.post("/{ingest_id}/stop", response_model=IngestRead)
async def stop_ingest(
    ingest_id: str,
    service: IngestServiceDep,
) -> IngestRead:
    """Останавливает ingest процесс."""
    return await service.stop_ingest(ingest_id)
