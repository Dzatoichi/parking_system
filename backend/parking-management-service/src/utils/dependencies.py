"""
src/utils/dependencies.py

Единое место для всех FastAPI-зависимостей проекта.

Правило: роутеры импортируют только отсюда — никаких локальных Depends.

Как использовать в роутере:
    from src.utils.dependencies import SpotServiceDep

    @router.get("/{spot_id}", response_model=SpotRead)
    async def get_spot(spot_id: int, service: SpotServiceDep) -> SpotRead:
        return await service.get_spot(spot_id)

Как подменить в тестах:
    from src.utils.dependencies import get_spot_service
    app.dependency_overrides[get_spot_service] = lambda: FakeSpotService()
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.base import db_helper
from src.services.spot_service import SpotService


async def get_session() -> AsyncSession:
    """
    Провайдер асинхронной сессии SQLAlchemy.
    Сессия открывается на один запрос и закрывается после его завершения.
    """
    async for session in db_helper.session_getter():
        yield session


# Annotated-алиас — используется как тип аргумента в роутерах и сервисах
SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_spot_service(session: SessionDep) -> SpotService:
    """
    Создаёт SpotService для текущего запроса, передавая ему сессию.
    Новый экземпляр на каждый запрос — гарантирует изоляцию транзакций.
    """
    return SpotService(session)


SpotServiceDep = Annotated[SpotService, Depends(get_spot_service)]