from typing import Any

import httpx

from src.schemas import SystemEventCreateSchema

class EventsClient:
    def __init__(self, base_url: str, timeout: int) -> None:
        self._base_url = base_url
        self._timeout = timeout

    async def send_device_event(
        self,
        event_data: SystemEventCreateSchema
    ) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(f"{self._base_url}/events", json=event_data.model_dump())
            response.raise_for_status()
            return response.json()
