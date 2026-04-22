from sqlalchemy import select, update

from src.dao.baseDAO import BaseDAO
from src.models.tokens.refresh_tokens import RefreshToken
from src.models.tokens.stateful_tokens import StatefulToken


class RefreshTokenDAO(BaseDAO[RefreshToken]):
    model = RefreshToken

    async def get_by_token_hash(self, token_hash: str) -> RefreshToken | None:
        stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def revoke(self, token_hash: str) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .values(revoked=True)
        )


class StatefulTokenDAO(BaseDAO[StatefulToken]):
    model = StatefulToken

    async def get_by_token(self, token: str) -> StatefulToken | None:
        stmt = select(StatefulToken).where(StatefulToken.token == token)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_as_used(self, token_id: int) -> None:
        await self.session.execute(
            update(StatefulToken)
            .where(StatefulToken.id == token_id)
            .values(used=True)
        )
