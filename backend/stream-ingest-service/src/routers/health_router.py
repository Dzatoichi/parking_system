"""
Healthcheck-роутер.
"""

from fastapi import APIRouter

health_router = APIRouter(tags=["health"])


@health_router.get("/health")
async def health() -> dict[str, str]:
    """Проверка доступности сервиса."""
    return {"status": "ok"}
