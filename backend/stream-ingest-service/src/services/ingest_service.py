"""
Service-слой Stream Ingest.
"""

import asyncio
import httpx
from fastapi import HTTPException, status

from src.clients.cv_client import CVServiceClient
from src.repositories.ingest_repository import IngestRepository
from src.schemas import IngestCreate, IngestRead
from src.services.stream_service import run_stream
from src.settings.config import Settings

_active_streams: dict[str, asyncio.Event] = {}


class IngestService:
    """Бизнес-логика ingest-обертки над CV сервисом."""

    def __init__(self, repository: IngestRepository, cv_client: CVServiceClient) -> None:
        self._repository = repository
        self._cv_client = cv_client
        self.devices = self._get_devices()

    async def start_ingest(self, payload: IngestCreate) -> IngestRead:
        """Запускает ingest, создает CV задачу и запускает поток с камеры."""
        cv_job = await self._create_cv_job(payload.model_dump(exclude={"dev"}))
        ingest = await self._repository.create(cv_job)

        server_ip = await self._get_server_ip(payload.dev)

        stop_event = asyncio.Event()
        _active_streams[ingest["ingest_id"]] = stop_event

        asyncio.create_task(
            run_stream(
                cv_job_id=cv_job["job_id"],
                dev=payload.dev,
                server_ip=server_ip,
                cv_client=self._cv_client,
                stop_event=stop_event,
            )
        )

        return self._to_read(ingest)

    async def get_ingest(self, ingest_id: str) -> IngestRead:
        """Возвращает ingest и подтягивает актуальный статус из CV."""
        ingest = await self._repository.get_by_id(ingest_id)
        if ingest is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ingest job not found",
            )

        cv_job = await self._get_cv_job(ingest["cv_job_id"])
        updated = await self._repository.update_status(ingest_id, cv_job)
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ingest job not found",
            )
        return self._to_read(updated)

    async def stop_ingest(self, ingest_id: str) -> IngestRead:
        """Останавливает ingest и видеопоток."""
        if ingest_id in _active_streams:
            _active_streams[ingest_id].set()
            del _active_streams[ingest_id]

        ingest = await self._repository.get_by_id(ingest_id)
        if ingest is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ingest job not found",
            )

        cv_job = await self._stop_cv_job(ingest["cv_job_id"])
        updated = await self._repository.update_status(ingest_id, cv_job)
        if updated is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Ingest job not found",
            )
        return self._to_read(updated)

    async def _get_server_ip(self, dev: str) -> str:
        """Получает IP сервера IPEYE для камеры."""
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"http://api.ipeye.ru/device/server/{dev}")
            data = r.json()
            if data.get("code") == 200:
                return data["message"]
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Не удалось получить сервер IPEYE для камеры {dev}",
            )

    async def _create_cv_job(self, payload: dict) -> dict:
        """Создает CV задачу с преобразованием ошибок транспорта в HTTP-ошибки API."""
        try:
            return await self._cv_client.create_job(payload)
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=f"cv-processing-service error: {exc.response.text}",
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"CV service unavailable: {exc}",
            ) from exc

    async def _get_cv_job(self, cv_job_id: str) -> dict:
        """Читает статус CV задачи с преобразованием ошибок транспорта."""
        try:
            return await self._cv_client.get_job(cv_job_id)
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=f"cv-processing-service error: {exc.response.text}",
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"CV service unavailable: {exc}",
            ) from exc

    async def _stop_cv_job(self, cv_job_id: str) -> dict:
        """Останавливает CV задачу с преобразованием ошибок транспорта."""
        try:
            return await self._cv_client.stop_job(cv_job_id)
        except httpx.HTTPStatusError as exc:
            raise HTTPException(
                status_code=exc.response.status_code,
                detail=f"cv-processing-service error: {exc.response.text}",
            ) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"CV service unavailable: {exc}",
            ) from exc

    @staticmethod
    def _to_read(ingest: dict) -> IngestRead:
        """Маппинг внутренней модели в API-DTO."""
        return IngestRead(
            ingest_id=ingest["ingest_id"],
            cv_job_id=ingest["cv_job_id"],
            status=ingest["status"],
            accepted_at=ingest["accepted_at"],
            details=ingest["details"],
        )

    async def _get_devices(self):
        """
        Получение всех параметров всех камер
        :return:
        """

        token =  Settings.AUTH_TOKEN

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(
                "https://ipeye.ru/api/rest/devices",
                headers=headers
            )
            devices = r.json()
            return devices