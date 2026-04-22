from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Класс конфига для работы с БД.
    """

    DB_HOST: str
    DB_PORT: str
    DB_USER: str
    DB_PASS: str
    DB_NAME: str
    JWT_ACCESS_SECRET_KEY: str
    JWT_REFRESH_SECRET_KEY: str
    JWT_REGISTER_SECRET_KEY: str
    JWT_ALGORITHM: str
    JWT_ACCESS_EXPIRE_TIME: int
    JWT_REFRESH_EXPIRE_TIME: int
    JWT_REGISTER_EXPIRE_TIME: int

    LOG_LEVEL: str
    LOG_TO_CONSOLE: bool
    LOGS_DIR: str

    STATEFUL_TOKEN_EXPIRE_MINUTES: int = 15

    model_config = SettingsConfigDict(env_file=".env")

    def CONNECT_ASYNC(self):
        """
        Функция создания соединения с БД.
        """
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASS}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    def get_jwt_params(self, token_type):
        """
        Функция получения параметров jwt токена.
        """
        jwt_params = {
            "algorithm": self.JWT_ALGORITHM,
        }
        if token_type == "access":
            added_jwt_params = {
                "secret_key": self.JWT_ACCESS_SECRET_KEY,
                "expire_time": self.JWT_ACCESS_EXPIRE_TIME,
            }
        elif token_type == "register":
            added_jwt_params = {
                "secret_key": self.JWT_REGISTER_SECRET_KEY,
                "expire_time": self.JWT_REGISTER_EXPIRE_TIME,
            }
        else:
            added_jwt_params = {
                "secret_key": self.JWT_REFRESH_SECRET_KEY,
                "expire_time": self.JWT_REFRESH_EXPIRE_TIME,
            }

        return jwt_params | added_jwt_params


settings = Settings()
