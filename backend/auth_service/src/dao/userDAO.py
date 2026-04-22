from sqlalchemy import delete, insert, select
from sqlalchemy.orm import selectinload

from src.dao.baseDAO import BaseDAO
from src.models.user_permissions import UserPermission
from src.models.users import User


class UserDAO(BaseDAO[User]):
    model = User

    async def get_by_email(self, email: str) -> User | None:
        stmt = (
            select(User)
            .options(
                selectinload(User.permission_links).selectinload(UserPermission.permission),
                selectinload(User.refresh_tokens),
                selectinload(User.reset_tokens),
            )
            .where(User.email == email)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_permissions(self, user_id: int) -> User | None:
        stmt = (
            select(User)
            .options(selectinload(User.permission_links).selectinload(UserPermission.permission))
            .where(User.id == user_id)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_user(self, payload: dict) -> User:
        return await self.create(payload)

    async def set_password(self, user_id: int, hashed_password: str) -> User | None:
        return await self.update(user_id, hashed_password=hashed_password)

    async def replace_permissions(self, user_id: int, permission_ids: list[int]) -> None:
        await self.session.execute(
            delete(UserPermission).where(UserPermission.user_id == user_id)
        )
        if permission_ids:
            await self.session.execute(
                insert(UserPermission),
                [{"user_id": user_id, "permission_id": permission_id} for permission_id in permission_ids],
            )
