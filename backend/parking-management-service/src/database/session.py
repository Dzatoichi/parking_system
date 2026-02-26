# database/session.py
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
    AsyncEngine
)
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool
from typing import AsyncGenerator
import os


class DatabaseManager:
    def __init__(self):
        self.engine: AsyncEngine | None = None
        self.async_session_maker: async_sessionmaker[AsyncSession] | None = None

    async def initialize(self):
        """Инициализация подключения к БД"""

        # URL подключения из переменных окружения
        DATABASE_URL = os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://parking_user:parking_pass@postgres-parking:5432/parking_db"
        )

        # Создаём движок с настройками пула соединений
        self.engine = create_async_engine(
            DATABASE_URL,
            echo=os.getenv("SQL_ECHO", "false").lower() == "true",  # Логи SQL
            pool_size=20,  # Размер пула
            max_overflow=10,  # Дополнительные соединения при пике
            pool_pre_ping=True,  # Проверка соединения перед использованием
            pool_recycle=3600,  # Пересоздавать соединения каждый час
        )

        # Создаём фабрику сессий
        self.async_session_maker = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )

    async def close(self):
        """Закрытие соединения"""
        if self.engine:
            await self.engine.dispose()

    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Получение сессии (для зависимостей FastAPI)"""
        if not self.async_session_maker:
            raise RuntimeError("Database not initialized")

        async with self.async_session_maker() as session:
            try:
                yield session
            finally:
                await session.close()


# Глобальный экземпляр менеджера БД
db_manager = DatabaseManager()


# Функция для FastAPI зависимостей
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async for session in db_manager.get_session():
        yield session