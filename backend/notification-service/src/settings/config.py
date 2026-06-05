from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    sqlite_path: str = "sqlite+aiosqlite:///./data/notifications.db"
    app_title: str = "Notification Service"
    default_channel: str = "push"
    push_provider: str = "fcm"
    fcm_project_id: str | None = None
    fcm_service_account_file: str = "/app/secrets/firebase-service-account.json"
    fcm_timeout_seconds: int = 10


settings = Settings()
