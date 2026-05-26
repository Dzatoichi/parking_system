from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    sqlite_path: str = "sqlite+aiosqlite:///./data/emulator.db"

    PARKING_MANAGMENT_SERVICE_URL: str
    PARKING_MANAGEMENT_TIMEOUT_SECONDS: int

settings = Settings()
