import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, status

from src.core.security.hash_helper import hash_helper
from src.core.security.token_handler import TokenHandler
from src.dao.tokensDAO import RefreshTokenDAO, StatefulTokenDAO
from src.models.tokens.stateful_tokens import StatefulToken
from src.schemas.enums import TokenType, UserRole
from src.settings.config import settings


class JWTTokensService:
    def __init__(self, refresh_token_dao: RefreshTokenDAO) -> None:
        self.refresh_token_dao = refresh_token_dao

    async def create_auth_tokens(self, user_id: int, role: UserRole) -> dict[str, str]:
        access_token, _ = TokenHandler(TokenType.ACCESS).sign_user_token(user_id=user_id, role=role)
        refresh_token, expires_at = TokenHandler(TokenType.REFRESH).sign_user_token(user_id=user_id, role=role)

        await self.refresh_token_dao.create(
            {
                "user_id": user_id,
                "token_hash": hash_helper.hash_token(refresh_token),
                "issued_at": datetime.now(timezone.utc),
                "expires_at": expires_at,
                "revoked": False,
            }
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        }

    async def revoke_refresh_token(self, token: str) -> None:
        await self.refresh_token_dao.revoke(hash_helper.hash_token(token))

    async def validate_refresh_token(self, token: str) -> dict:
        try:
            payload = TokenHandler(TokenType.REFRESH).decode(token)
        except jwt.PyJWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            ) from exc

        token_hash = hash_helper.hash_token(token)
        token_record = await self.refresh_token_dao.get_by_token_hash(token_hash)
        if not token_record or token_record.revoked:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked",
            )

        return payload

    def validate_access_token(self, token: str) -> dict:
        try:
            return TokenHandler(TokenType.ACCESS).decode(token)
        except jwt.PyJWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token",
            ) from exc

    def create_register_token(self, email: str, role: UserRole, full_name: str | None = None) -> str:
        token, _ = TokenHandler(TokenType.REGISTER).sign_register_token(
            email=email,
            role=role,
            full_name=full_name,
        )
        return token

    def validate_register_token(self, token: str) -> dict:
        try:
            return TokenHandler(TokenType.REGISTER).decode(token)
        except jwt.PyJWTError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid registration token",
            ) from exc


class StatefulTokenService:
    def __init__(self, dao: StatefulTokenDAO) -> None:
        self.dao = dao

    async def create_reset_token(self, user_id: int) -> StatefulToken:
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.STATEFUL_TOKEN_EXPIRE_MINUTES)
        return await self.dao.create(
            {
                "token": secrets.token_urlsafe(32),
                "user_id": user_id,
                "expires_at": expires_at,
                "used": False,
            }
        )

    async def validate_reset_token(self, token: str) -> StatefulToken:
        token_obj = await self.dao.get_by_token(token)
        if not token_obj or token_obj.used or token_obj.expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Reset token is invalid or expired",
            )
        return token_obj

    async def mark_token_as_used(self, token_id: int) -> None:
        await self.dao.mark_as_used(token_id)
