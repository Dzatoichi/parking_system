"""
DTO-схемы для операций с CV задачами.
"""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from src.schemas.base_schema import BaseSchema

JobStatus = Literal["queued", "running", "completed", "failed", "stopped"]


class CVJobCreate(BaseSchema):
    """Входной payload для запуска обработки потока."""

    camera_id: str = Field(..., min_length=1)
    stream_url: str = Field(..., min_length=1)
    correlation_id: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class CVJobRead(BaseSchema):
    """Ответ API по состоянию CV задачи."""

    job_id: str
    status: JobStatus
    accepted_at: datetime
    details: dict[str, Any] = Field(default_factory=dict)
