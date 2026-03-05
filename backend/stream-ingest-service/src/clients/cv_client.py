"""
HTTP-клиент для взаимодействия с cv-processing-service.
"""

from typing import Any

import httpx

from src.settings.config import settings


class CVServiceClient:
    """Транспортный слой к API CV сервиса."""

    def __init__(self) -> None:
        self._base_url = settings.CV_SERVICE_URL.rstrip("/")
        self._timeout = settings.CV_SERVICE_TIMEOUT_SECONDS

    async def create_job(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Создает CV задачу."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(f"{self._base_url}/v1/jobs", json=payload)
            response.raise_for_status()
            return response.json()

    async def get_job(self, cv_job_id: str) -> dict[str, Any]:
        """Возвращает статус CV задачи."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(f"{self._base_url}/v1/jobs/{cv_job_id}")
            response.raise_for_status()
            return response.json()

    async def stop_job(self, cv_job_id: str) -> dict[str, Any]:
        """Останавливает CV задачу."""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(f"{self._base_url}/v1/jobs/{cv_job_id}/stop")
            response.raise_for_status()
            return response.json()
