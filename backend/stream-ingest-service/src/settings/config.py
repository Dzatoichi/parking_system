"""
Конфигурация Stream Ingest сервиса.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения из env/.env."""

    APP_TITLE: str = "Stream Ingest Service"
    CV_SERVICE_URL: str = "http://cv-processing-service:8001"
    CV_SERVICE_TIMEOUT_SECONDS: float = 10.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
