from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.settings.config import settings


class Base(DeclarativeBase):
    """
    Базовый класс для моделей. Все модели наследуются от него.
    """

    pass


class DataBaseHelper:
    """
    Вспомогательный класс для  работы с БД.
    """

    def __init__(self):
        self.engine = create_async_engine(
            url=settings.CONNECT_ASYNC(),
            echo=False,
        )
        self.async_session_maker = async_sessionmaker(
            bind=self.engine,
            expire_on_commit=False,
        )

    async def session_getter(self):
        async with self.async_session_maker() as session:
            yield session


db_helper = DataBaseHelper()
