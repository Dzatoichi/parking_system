from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    """
    Класс конфига для работы с БД.
    """

    DATABASE_URL: str | None = None

    AUTH_SERVICE_URL: str
    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/"
    BOOKING_EVENTS_EXCHANGE: str = "booking.events"
    BOOKING_EVENTS_QUEUE: str = "booking.projection"
    CV_EVENTS_EXCHANGE: str = "parking.cv"
    CV_EVENTS_QUEUE: str = "parking.cv.events"

    DB_HOST: str = "localhost"
    DB_PORT: str = "5432"
    DB_USER: str = "parking_user"
    DB_PASS: str = "parking_pass"
    DB_NAME: str = "parking_db"
    JWT_ACCESS_SECRET_KEY: str = "dev-access-secret"
    JWT_REFRESH_SECRET_KEY: str = "dev-refresh-secret"
    JWT_REGISTER_SECRET_KEY: str = "dev-register-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_EXPIRE_TIME: int = 15
    JWT_REFRESH_EXPIRE_TIME: int = 10080
    JWT_REGISTER_EXPIRE_TIME: int = 30

    LOG_LEVEL: str = "INFO"
    LOG_TO_CONSOLE: bool = True
    LOGS_DIR: str = "logs"

    STATEFUL_TOKEN_EXPIRE_MINUTES: int = 15

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    def CONNECT_ASYNC(self) -> str:
        """
        Функция создания соединения с БД.
        """
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}"
            f"@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"
        )


settings = Settings()
