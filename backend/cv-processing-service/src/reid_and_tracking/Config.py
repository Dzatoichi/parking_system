from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Класс конфига для работы с БД и моделями.
    """
    DB_HOST: str
    DB_PORT: str
    DB_USER: str
    DB_PASS: str
    DB_NAME: str

    OSNET_MODEL_PATH: str
    YOLO_PLATE_MODEL_PATH: str
    YOLO_CAR_MODEL_PATH: str
    OCR_MODEL_PATH: str

    DEVICE: str

    model_config = SettingsConfigDict(env_file='src/.env')

settings = Settings()
