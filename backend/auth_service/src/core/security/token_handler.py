from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import jwt

from src.schemas.enums import TokenType, UserRole
from src.settings.config import settings


class TokenHandler:
    def __init__(self, token_type: TokenType) -> None:
        self.token_type = token_type
        self.algorithm, self.key, self.expire_time = settings.jwt_params(token_type.value)

    def sign_user_token(self, user_id: int, role: UserRole) -> tuple[str, datetime]:
        if self.token_type == TokenType.REFRESH:
            ttl = timedelta(days=self.expire_time)
        else:
            ttl = timedelta(minutes=self.expire_time)

        expires_at = datetime.now(timezone.utc) + ttl
        payload = {
            "sub": str(user_id),
            "role": role.value,
            "type": self.token_type.value,
            "exp": expires_at,
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid4()),
        }
        token = jwt.encode(payload, self.key, algorithm=self.algorithm)
        return token, expires_at

    def sign_register_token(self, email: str, role: UserRole, full_name: str | None = None) -> tuple[str, datetime]:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=self.expire_time)
        payload = {
            "email": email,
            "role": role.value,
            "full_name": full_name,
            "type": self.token_type.value,
            "exp": expires_at,
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid4()),
        }
        token = jwt.encode(payload, self.key, algorithm=self.algorithm)
        return token, expires_at

    def decode(self, token: str) -> dict[str, Any]:
        return jwt.decode(
            token,
            self.key,
            algorithms=[self.algorithm],
            options={"require": ["exp", "type"]},
        )
