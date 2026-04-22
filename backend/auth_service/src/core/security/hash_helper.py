import hashlib

import bcrypt


class HashHelper:
    """
    Класс для обработки паролей и хеширования токенов.
    """

    def hash(self, plain_str: str) -> str:
        """Метод хеширования строк"""
        return bcrypt.hashpw(plain_str.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Проверяет пароль по его хешу"""
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )

    def hash_token(self, token: str) -> str:
        """
        Метод хеширования токенов (deterministic).
        """
        return hashlib.sha256(token.encode()).hexdigest()


hash_helper = HashHelper()
