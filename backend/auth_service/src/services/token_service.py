import secrets
from datetime import datetime, timedelta, timezone

from src.core.security.token_handler import TokenHandler
from src.dao.tokensDAO import RefreshTokensDAO, StatefulTokenDAO
from src.models.tokens.stateful_tokens import StatefulTokens
from src.schemas.enums import PositionSourceEnum
from src.schemas.tokens_schemas import TokenTypesEnum
from src.settings.config import settings
from src.utils.exceptions import (
    InvalidTokenException,
    TokenExpiredException,
)


class JWTTokensService:
    """
    Класс сервиса для работы с jwt токенами.
    """

    def __init__(self, repo: RefreshTokensDAO) -> None:
        self.repo = repo

    async def create_token(
        self,
        token_type: TokenTypesEnum,
        user_id: int,
    ) -> str:
        """
        Функция генерации access или refresh токена.
        """
        token_handler = TokenHandler(token_type=token_type)
        token, expires_at = token_handler.sign_jwt(user_id=user_id)

        if token_type == TokenTypesEnum.refresh:
            token_hash = hash_helper.hash_token(token=token)
            payload = {
                "user_id": user_id,
                "token_hash": token_hash,
                "issued_at": datetime.now(timezone.utc),
                "expires_at": expires_at,
            }
            await self.repo.create(payload=payload)

        return token

    async def create_register_token(
        self,
        token_type: TokenTypesEnum,
        pvz_id: int,
        owner_id: int,
        position_id: int,
        position_source: PositionSourceEnum,
    ) -> str:
        """
        Создание JWT токена для регистрации сотрудника.
        """

        token_handler = TokenHandler(token_type=token_type)
        token, expires_at = token_handler.sign_register_jwt(
            pvz_id=pvz_id,
            owner_id=owner_id,
            position_id=position_id,
            position_source=position_source,
        )
        return token

    async def revoke_token(
        self,
        token: str,
    ) -> bool:
        """
        Функция для обозначения токена, как отозванного.
        """

        token_hash = hash_helper.hash_token(token=token)
        await self.repo.set_token_revoked(token_hash=token_hash)

        return True

    async def refresh_token(
        self,
        refresh_token: str,
    ) -> dict[str, str]:
        """
        Функция для обновления access-токена, выдачи нового refresh-токена.
        """
        token_payload = await self.validate_token(
            token=refresh_token,
            token_type=TokenTypesEnum.refresh,
        )

        access_token = await self.create_token(
            token_type=TokenTypesEnum.access,
            user_id=token_payload.get("user_id"),
        )

        await self.revoke_token(
            token=refresh_token,
        )

        new_refresh_token = await self.create_token(
            token_type=TokenTypesEnum.refresh,
            user_id=token_payload.get("user_id"),
        )
        return {
            "access_token": access_token,
            "refresh_token": new_refresh_token,
        }

    async def validate_token(self, token: str, token_type: TokenTypesEnum) -> dict:
        """
        Функция для валидации refresh или access токена.
        """
        token_handler = TokenHandler(token_type=token_type)

        token_payload = token_handler.decode_jwt(token=token)
        if not token_payload:
            raise InvalidTokenException("Invalid token")

        exp_time = datetime.fromtimestamp(token_payload.get("exp"), tz=timezone.utc)
        if exp_time < datetime.now(timezone.utc):
            raise TokenExpiredException("Token expired")

        if token_type == TokenTypesEnum.access:
            return token_payload

        if token_type == TokenTypesEnum.register:
            required_fields = ["pvz_id", "owner_id"]
            for field in required_fields:
                if field not in token_payload:
                    raise InvalidTokenException(f"Missing required field: {field}")
            return token_payload

        token_hash = hash_helper.hash_token(token=token)
        token_info = await self.repo.get_token_by_token_hash(token_hash=token_hash)

        if not token_info or token_info.revoked:
            raise InvalidTokenException("Invalid token")

        return token_payload


class StatefulTokenService:
    """
    Класс сервиса обработки stateful токенов.
    """

    def __init__(self, dao: StatefulTokenDAO) -> None:
        self.dao = dao

    async def create_stateful_token(
        self,
        user_id: int,
    ):
        """
        Метод генерации stateful токена и его возвращении в виде строки.
        """

        token_str = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.STATEFUL_TOKEN_EXPIRE_MINUTES)

        payload = {
            "token": token_str,
            "user_id": user_id,
            "expires_at": expires_at,
            "used": False,
        }
        return await self.dao.create(payload)

    async def get_reset_token_data(self, token: str) -> StatefulTokens | None:
        """
        Метод получения данных токена и его валиадации.
        """
        return await self.validate_token(token)

    async def mark_token_as_used(
        self,
        token_obj: StatefulTokens,
    ) -> None:
        """
        Метод пометки токена, как использованного.
        """
        await self.dao.mark_as_used(token_obj.id)

    async def validate_token(
        self,
        token: str,
    ) -> StatefulTokens | None:
        """
        Метод валидации stateful токена.
        """
        token_obj = await self.dao.get_by_token(token)
        if not token_obj or token_obj.used or token_obj.expires_at < datetime.now(timezone.utc):
            return None
        return token_obj
