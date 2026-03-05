"""
Точка входа Stream Ingest API.

Здесь только сборка приложения и подключение роутеров.
"""

from fastapi import FastAPI

from src.routers.health_router import health_router
from src.routers.ingest_router import ingest_router
from src.settings.config import settings

app = FastAPI(title=settings.APP_TITLE)

# Базовые маршруты сервиса.
app.include_router(health_router)
app.include_router(ingest_router)
