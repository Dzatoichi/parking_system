from sqlalchemy import select

from src.dao.baseDAO import BaseDAO
from src.models.permissions import Permission


class PermissionDAO(BaseDAO[Permission]):
    model = Permission

    async def get_by_codes(self, codes: list[str]) -> list[Permission]:
        if not codes:
            return []
        stmt = select(Permission).where(Permission.code_name.in_(codes))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create_if_missing(self, code_name: str, description: str | None = None) -> Permission:
        existing = await self.get_by_code(code_name)
        if existing:
            return existing
        return await self.create({"code_name": code_name, "description": description})

    async def get_by_code(self, code_name: str) -> Permission | None:
        stmt = select(Permission).where(Permission.code_name == code_name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
