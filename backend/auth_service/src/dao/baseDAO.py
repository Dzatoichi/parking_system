from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from sqlalchemy import delete, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.base import Base, db_helper

T = TypeVar("T", bound=Base)


class BaseDAO(Generic[T]):
    """
    Базовый класс DAO для работы с ORM-моделями.
    """

    def __init__(self, model: Optional[Type[T]] = None):
        """
        Метод инициализации.
        """
        if model is not None:
            self.model = model

        if not hasattr(self, "model") or self.model is None:
            raise TypeError("Отсутствует модель")

        self._db_helper = db_helper

    @asynccontextmanager
    async def _get_session(self) -> AsyncSession:
        """
        Метод получения сессии.
        """
        async with self._db_helper.async_session_maker() as session:
            try:
                yield session
            except SQLAlchemyError as e:
                await session.rollback()
                raise e
            finally:
                await session.close()

    @staticmethod
    def with_exception(func):
        """
        Декоратор, оборачивающий метод для обработки и проброса исключения дальше.
        """

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except SQLAlchemyError as e:
                raise e
            except Exception as e:
                raise e

        return async_wrapper

    @with_exception
    async def create(self, payload: Dict[str, Any]) -> T:
        """
        Базовый метод создания сущности.
        """
        obj = self.model(**payload)
        async with self._get_session() as session:
            session.add(obj)
            await session.commit()
            await session.refresh(obj)
            return obj

    @with_exception
    async def get_by_id(self, id: int) -> Optional[T]:
        """
        Базовый метод получения сущности по id.
        """
        stmt = select(self.model).where(self.model.id == id)
        async with self._get_session() as session:
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    @with_exception
    async def get_all(self) -> List[T]:
        """
        Базовый метод получения сущностей.
        """
        stmt = select(self.model)
        async with self._get_session() as session:
            result = await session.execute(stmt)
            return result.scalars().all()

    @with_exception
    async def update(self, id: int, **kwargs) -> Optional[T]:
        """
        Базовый метод изменения сущностей.
        """
        async with self._get_session() as session:
            stmt = update(self.model).where(self.model.id == id).values(**kwargs).returning(self.model)
            result = await session.execute(stmt)
            await session.commit()
            updated = result.scalar_one_or_none()
            if updated:
                await session.refresh(updated)
            return updated

    @with_exception
    async def delete(self, id: int) -> bool:
        """
        Базовый метод удаления сущностей.
        """
        async with self._get_session() as session:
            stmt = delete(self.model).where(self.model.id == id)
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount > 0
