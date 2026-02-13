import logging
from typing import List, Optional

import psycopg2
from psycopg2 import OperationalError

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DatabaseManager:
    """Класс для управления подключением и операциями с базой данных"""

    def __init__(self, database: str, user: str, password: str,
                 host: str, port: str):
        self.db_config = {
            'database': database,
            'user': user,
            'password': password,
            'host': host,
            'port': port,
        }
        self.connection = None

    def connect(self) -> bool:
        """Устанавливает подключение к базе данных"""
        try:
            self.connection = psycopg2.connect(**self.db_config)
            logger.info("Успешное подключение к PostgreSQL")
            return True
        except OperationalError as e:
            logger.error(f"Ошибка подключения к базе данных: {e}")
            return False

    def disconnect(self):
        """Закрывает подключение к базе данных"""
        if self.connection:
            self.connection.close()
            logger.info("Подключение к базе данных закрыто")

    def execute_query(self, query: str, params: Optional[tuple] = None) -> bool:
        """Выполняет SQL запрос с обработкой ошибок"""
        if not self.connection:
            logger.error("Нет подключения к базе данных")
            return False

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, params)
                self.connection.commit()
                logger.debug("Запрос выполнен успешно")
                return True
        except OperationalError as e:
            logger.error(f"Ошибка выполнения запроса: {e}")
            self.connection.rollback()
            return False

    def execute_read_query(self, query: str, params: Optional[tuple] = None) -> List[tuple]:
        """Выполняет SQL запрос на чтение данных"""
        if not self.connection:
            logger.error("Нет подключения к базе данных")
            return []

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(query, params)
                return cursor.fetchall()
        except OperationalError as e:
            logger.error(f"Ошибка выполнения запроса на чтение: {e}")
            return []
