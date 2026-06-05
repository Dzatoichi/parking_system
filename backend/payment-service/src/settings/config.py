from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    sqlite_path: str = "sqlite+aiosqlite:///./data/payments.db"
    app_title: str = "Payment Service"
    mock_payment_base_url: str = "http://localhost:8005/mock-payments"


settings = Settings()
