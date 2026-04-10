"""
DTO-схемы для stream ingest API.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from src.schemas.base_schema import BaseSchema

IngestStatus = Literal["queued", "running", "completed", "failed", "stopped"]


class IngestCreate(BaseSchema):
    """Входной payload для запуска ingest."""

    camera_id: str = Field(..., min_length=1)
    stream_url: str = Field(..., min_length=1)
    dev: str = Field(..., min_length=1)  # <- добавить это поле (dev из IPEYE)
    correlation_id: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class IngestRead(BaseSchema):
    """Ответ API по состоянию ingest-задачи."""

    ingest_id: str
    cv_job_id: str
    status: IngestStatus
    accepted_at: datetime
    details: dict[str, Any] = Field(default_factory=dict)
