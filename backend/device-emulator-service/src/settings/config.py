from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    sqlite_path: str = "sqlite+aiosqlite:///./data/emulator.db"

    PARKING_MANAGEMENT_SERVICE_URL: str = Field(
        default="http://parking-management-service:8000",
        validation_alias=AliasChoices(
            "PARKING_MANAGEMENT_SERVICE_URL",
            "PARKING_MANAGMENT_SERVICE_URL",
        ),
    )
    PARKING_MANAGEMENT_TIMEOUT_SECONDS: int = 5

settings = Settings()
