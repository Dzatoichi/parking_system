from typing import Any

import httpx

from src.api.settings.config import settings


class ParkingManagementClient:
    def __init__(self) -> None:
        self._base_url = settings.PARKING_MANAGEMENT_URL.rstrip("/")
        self._timeout = settings.PARKING_MANAGEMENT_TIMEOUT_SECONDS

    async def get_monitoring_config(self, camera_id: int) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(f"{self._base_url}/internal/cv/cameras/{camera_id}/monitoring-config")
            response.raise_for_status()
            return response.json()
