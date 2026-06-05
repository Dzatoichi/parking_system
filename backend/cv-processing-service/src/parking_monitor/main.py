# main.py

import argparse
import time
import signal
import sys
from psycopg2 import pool

from parking_monitor.db.repository import ParkingRepository
from parking_monitor.core.parking_monitor import ParkingMonitor


def main():
    # Создаем пул соединений
    db_pool = pool.SimpleConnectionPool(
        minconn=1,
        maxconn=10,
        dbname="parking_db",
        user="postgres",
        password="",
        host="localhost",
        port=5432
    )

    try:
        # Создаем репозиторий
        repo = ParkingRepository(db_pool)

        # Создаем монитор
        monitor = ParkingMonitor(repo)

        # Считываем конфигурацию из БД
        monitor.initialize_from_db()

        # Обработка сигналов для graceful shutdown
        def signal_handler(sig, frame):
            print("\nShutting down...")
            monitor.stop()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Запускаем монитор
        monitor.start()

        # Главный цикл (можно заменить на веб-сервер или GUI)
        print("\nParking Monitoring System is running\n")

        while True:
            time.sleep(5)

    finally:
        db_pool.closeall()


if __name__ == "__main__":
    main()