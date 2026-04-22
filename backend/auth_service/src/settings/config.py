from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_TITLE: str = "Auth Service"

    DB_HOST: str
    DB_PORT: int
    DB_USER: str
    DB_PASS: str
    DB_NAME: str

    JWT_ACCESS_SECRET_KEY: str
    JWT_REFRESH_SECRET_KEY: str
    JWT_REGISTER_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_TIME: int = 15
    JWT_REFRESH_EXPIRE_TIME: int = 7
    JWT_REGISTER_EXPIRE_TIME: int = 24

    LOG_LEVEL: str = "INFO"
    LOG_TO_CONSOLE: bool = True
    LOGS_DIR: str = "logs"

    STATEFUL_TOKEN_EXPIRE_MINUTES: int = 15

    BOOTSTRAP_ADMIN_ENABLED: bool = True
    BOOTSTRAP_ADMIN_EMAIL: str = "admin@mail.ru"
    BOOTSTRAP_ADMIN_PASSWORD: str = Field(default="Admin12345!", min_length=8)
    BOOTSTRAP_ADMIN_FULL_NAME: str = "System Admin"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )

    def jwt_params(self, token_type: str) -> tuple[str, str, int]:
        if token_type == "access":
            return self.JWT_ALGORITHM, self.JWT_ACCESS_SECRET_KEY, self.JWT_ACCESS_EXPIRE_TIME
        if token_type == "register":
            return self.JWT_ALGORITHM, self.JWT_REGISTER_SECRET_KEY, self.JWT_REGISTER_EXPIRE_TIME
        return self.JWT_ALGORITHM, self.JWT_REFRESH_SECRET_KEY, self.JWT_REFRESH_EXPIRE_TIME


settings = Settings()
