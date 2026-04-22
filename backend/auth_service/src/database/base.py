from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from src.settings.config import settings


class Base(DeclarativeBase):
    pass


engine = create_async_engine(
    settings.database_url,
    echo=False,
)

async_session_maker = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


class DataBaseHelper:
    def __init__(self) -> None:
        self.engine = engine
        self.async_session_maker = async_session_maker

    async def session_getter(self) -> AsyncIterator[AsyncSession]:
        async with self.async_session_maker() as session:
            yield session


db_helper = DataBaseHelper()


async def init_models() -> None:
    import src.models  # noqa: F401

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
