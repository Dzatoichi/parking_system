"""
tests/conftest.py

Общие фикстуры для всех тестов.

Архитектура тестовой базы:
  - Используется SQLite (in-memory) — не нужен реальный PostgreSQL для CI
  - Каждый тест получает чистую БД через откат транзакции после теста
  - event_loop создаётся один раз на всю сессию (scope="session")
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)

from src.database.base import Base
from src.models.spots.spot import Spot  # noqa: F401 — нужен для Base.metadata
from src.routers.spots_router import spots_router
from src.utils.dependencies import get_spot_service
from src.services.spot_service import SpotService

from fastapi import FastAPI

# ──────────────────────────────────────────────────────────────
# Тестовый движок: SQLite in-memory
# ──────────────────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture(scope="session")
async def engine():
    """Создаём движок и схему один раз на всю сессию тестов."""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        # echo=True,  # раскомментировать для отладки SQL
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncSession:
    """
    Каждый тест получает сессию внутри отдельной транзакции.
    После теста транзакция откатывается — БД остаётся чистой.

    Это быстрее, чем пересоздавать таблицы перед каждым тестом.
    """
    async with engine.begin() as conn:
        # Вложенная транзакция (SAVEPOINT) — откатывается после теста
        async with AsyncSession(bind=conn, expire_on_commit=False) as sess:
            await sess.begin_nested()
            yield sess
            await sess.rollback()


# ──────────────────────────────────────────────────────────────
# FastAPI тестовое приложение
# ──────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def app(session: AsyncSession):
    """
    Создаёт тестовое FastAPI-приложение с подменённой зависимостью сессии.
    get_spot_service переопределяется так, чтобы использовать тестовую сессию.
    """
    test_app = FastAPI()
    test_app.include_router(spots_router)

    # Подменяем зависимость: вместо реальной БД — тестовая сессия
    def override_get_spot_service() -> SpotService:
        return SpotService(session)

    test_app.dependency_overrides[get_spot_service] = override_get_spot_service
    return test_app


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncClient:
    """HTTP-клиент для e2e тестов роутера."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


# ──────────────────────────────────────────────────────────────
# Фабрики тестовых данных
# ──────────────────────────────────────────────────────────────

def make_spot(
    parking_id: int = 1,
    spot_number: str = "A-01",
    **kwargs,
) -> Spot:
    """Создаёт ORM-объект Spot с разумными дефолтами."""
    from src.models.spots.status.spot_status import SpotStatus
    from src.models.spots.type.spot_type import SpotType

    defaults = dict(
        parking_id=parking_id,
        spot_number=spot_number,
        spot_type=SpotType.STANDARD,
        spot_status=SpotStatus.FREE,
        spot_coordinates={
            "points": [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]],
            "center_x": 5.0,
            "center_y": 5.0,
        },
    )
    defaults.update(kwargs)
    return Spot(**defaults)


def make_spot_create_payload(
    spot_number: str = "A-01",
    spot_type: str = "standard",
) -> dict:
    """JSON-тело для POST /spots/{parking_id}."""
    return {
        "spot_number": spot_number,
        "spot_type": spot_type,
        "spot_coordinates": {
            "points": [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0]],
            "center_x": 5.0,
            "center_y": 5.0,
        },
    }
