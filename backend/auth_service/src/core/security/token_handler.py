import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from src.schemas.enums import PositionSourceEnum
from src.schemas.tokens_schemas import TokenTypesEnum
from src.settings.config import settings


class TokenHandler:
    """
    Класс для обработки jwt токенов.
    """

    def __init__(self, token_type: TokenTypesEnum) -> None:
        """
        Метод инициализации.
        """
        self.token_type = token_type
        self.algorithm, self.key, self.expire_time = settings.get_jwt_params(token_type=token_type).values()

    def sign_jwt(self, user_id: int) -> tuple[Any, datetime | int | None]:
        """
        Метод шифрования jwt токена.
        """
        if self.token_type == "refresh":
            expire_time = timedelta(days=self.expire_time)
        else:
            expire_time = timedelta(minutes=self.expire_time)
        payload = {
            "user_id": user_id,
            "exp": datetime.now(timezone.utc) + expire_time,
            "jti": str(uuid.uuid4()),
        }
        token = jwt.encode(
            payload=payload,
            key=self.key,
            algorithm=self.algorithm,
        )
        return token, payload.get("exp")

    def sign_register_jwt(
        self,
        pvz_id: int,
        owner_id: int,
        position_id: int,
        position_source: PositionSourceEnum,
    ) -> tuple[Any, datetime | int | None]:
        """
        Метод шифрования register jwt токена с дополнительными данными.
        """
        if self.token_type != TokenTypesEnum.register:
            raise ValueError("This method can only be used for registration tokens")

        expire_time = timedelta(hours=self.expire_time)

        payload = {
            "pvz_id": pvz_id,
            "owner_id": owner_id,
            "position_id": position_id,
            "position_source": position_source,
            "exp": datetime.now(timezone.utc) + expire_time,
        }

        token = jwt.encode(
            payload=payload,
            key=self.key,
            algorithm=self.algorithm,
        )
        return token, payload.get("exp")

    def decode_jwt(self, token: str) -> dict | None:
        """
        Метод дешифрования jwt токена.
        """
        try:
            return jwt.decode(
                token,
                key=self.key,
                algorithms=[self.algorithm],
                options={"require": ["exp"]},
            )
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
