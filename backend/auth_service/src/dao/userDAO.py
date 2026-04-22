from fastapi_pagination import Page, Params
from fastapi_pagination.ext.sqlalchemy import apaginate
from pydantic import EmailStr
from sqlalchemy import delete, insert, select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from src.dao.baseDAO import BaseDAO
from src.models.user_permissions.user_permissions import UserPermissions
from src.models.users.users import Users


class UserDAO(BaseDAO[Users]):
    """
    Класс, наследующий базовый DAO для работы с сущностями пользователя.
    """

    def __init__(self):
        super().__init__(model=Users)

    @BaseDAO.with_exception
    async def get_user_by_email(self, email: EmailStr) -> Users | None:
        """
        Метод получения пользователя по email.
        """
        async with self._get_session() as session:
            stmt = select(self.model).where(self.model.email == email)
            res = await session.execute(stmt)
            return res.scalars().first()

    @BaseDAO.with_exception
    async def get_users_by_ids(self, user_ids: list[int]) -> list[Users]:
        """
        Получает список пользователей по списку их ID одним запросом.
        WHERE id IN (...)
        """
        async with self._get_session() as session:
            stmt = select(self.model).where(self.model.id.in_(user_ids))
            res = await session.execute(stmt)
            return list(res.scalars().all())

    @BaseDAO.with_exception
    async def set_password(self, user_id: int, hashed_password: str) -> bool:
        """
        Метод изменения пароля.
        """
        updated_user = await self.update(id=user_id, hashed_password=hashed_password)
        if not updated_user:
            raise NoResultFound(f"Пользователь с id={user_id} не найден")
        return True

    @BaseDAO.with_exception
    async def assign_permissions(self, user_id: int, permissions: list[int], session: AsyncSession) -> None:
        """Назначает пользователю список permissions"""
        stmt = insert(UserPermissions).values([{"user_id": user_id, "permission_id": p_id} for p_id in permissions])
        await session.execute(stmt)

    @BaseDAO.with_exception
    async def create_user(self, payload: dict, session: AsyncSession) -> Users:
        """Метод создания пользователя"""
        user = self.model(**payload)
        session.add(user)
        await session.flush()
        return user

    @BaseDAO.with_exception
    async def update_user_permissions(
        self,
        session: AsyncSession,
        user_id: int,
        new_permission_ids: list[int],
    ) -> None:
        """Полностью обновляет права пользователя: удаляет все старые и вставляет новые."""

        await session.execute(delete(UserPermissions).where(UserPermissions.user_id == user_id))

        await session.execute(
            insert(UserPermissions).values([{"user_id": user_id, "permission_id": p_id} for p_id in new_permission_ids])
        )

    @BaseDAO.with_exception
    async def get_users(
        self,
        params: Params,
    ) -> Page[Users]:
        """
        Получает список пользователей с пагинацией.
        """
        async with self._get_session() as session:
            stmt = select(self.model)

            stmt = stmt.order_by(self.model.id.desc())

            return await apaginate(session, stmt, params)

    async def update_users_permissions(self, user_ids: list[int], permission_ids: list[int]) -> None:
        """
        Массовое обновление прав.
        Сначала удаляет старые, потом пишет новые.
        """
        async with self._get_session() as session:
            stmt_delete = delete(UserPermissions).where(UserPermissions.user_id.in_(user_ids))
            await session.execute(stmt_delete)

            values_to_insert = [
                {"user_id": u_id, "permission_id": p_id} for u_id in user_ids for p_id in permission_ids
            ]

            stmt_insert = insert(UserPermissions).values(values_to_insert)
            await session.execute(stmt_insert)
            await session.commit()
