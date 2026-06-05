"""
Конфигурация CV Processing сервиса.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения из env/.env."""

    APP_TITLE: str = "CV Processing Service"
    PARKING_MANAGEMENT_URL: str = "http://parking-management-service:8000"
    PARKING_MANAGEMENT_TIMEOUT_SECONDS: float = 5.0
    RABBITMQ_URL: str = "amqp://guest:guest@rabbitmq:5672/"
    CV_EVENTS_EXCHANGE: str = "parking.cv"
    CV_OCCUPANCY_DEBOUNCE_SECONDS: float = 3.0
    CV_DEFAULT_FPS: float = 10.0
    YOLO_MODEL_PATH: str = "yolo11n.pt"
    PARKING_DB_NAME: str = "parking_db"
    PARKING_DB_USER: str = "parking_user"
    PARKING_DB_PASSWORD: str = "parking_pass"
    PARKING_DB_HOST: str = "postgres-parking"
    PARKING_DB_PORT: int = 5432
    PARKING_DB_POOL_MIN: int = 1
    PARKING_DB_POOL_MAX: int = 10

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
