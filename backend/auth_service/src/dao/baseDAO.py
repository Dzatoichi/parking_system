from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseDAO(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, payload: dict[str, Any]) -> ModelT:
        entity = self.model(**payload)
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def get_by_id(self, entity_id: int) -> ModelT | None:
        stmt = select(self.model).where(self.model.id == entity_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self) -> Sequence[ModelT]:
        stmt = select(self.model).order_by(self.model.id.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def update(self, entity_id: int, **kwargs: Any) -> ModelT | None:
        stmt = update(self.model).where(self.model.id == entity_id).values(**kwargs).returning(self.model)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete(self, entity_id: int) -> bool:
        stmt = delete(self.model).where(self.model.id == entity_id)
        result = await self.session.execute(stmt)
        return bool(result.rowcount)
