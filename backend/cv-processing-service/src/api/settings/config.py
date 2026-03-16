"""
Конфигурация CV Processing сервиса.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения из env/.env."""

    APP_TITLE: str = "CV Processing Service"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
