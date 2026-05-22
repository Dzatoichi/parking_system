# main.py

import argparse
import time
import signal
import sys
from psycopg2 import pool

from parking_monitor.db.repository import ParkingRepository
from parking_monitor.core.parking_monitor import ParkingMonitor


def create_db_pool():
    """Создает пул соединений с БД"""
    return pool.SimpleConnectionPool(
        minconn=1,
        maxconn=10,
        dbname="parking_db",
        user="postgres",
        password="",  # из конфига
        host="localhost",
        port=5432
    )


def main():
    parser = argparse.ArgumentParser(description="Parking Monitoring System")
    parser.add_argument("--init-db", action="store_true", help="Initialize database (create tables)")
    parser.add_argument("--config", type=str, default="config.json", help="Configuration file")
    args = parser.parse_args()

    # Создаем пул соединений
    db_pool = create_db_pool()

    try:
        # Создаем репозиторий
        repo = ParkingRepository(db_pool)

        # Создаем монитор
        monitor = ParkingMonitor(repo)

        # Инициализируем из БД
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
        print("\nParking Monitoring System is running. Press Ctrl+C to stop.\n")

        while True:
            time.sleep(5)
            status = monitor.get_status()
            print(f"Status: {status['active_vehicles']} active, "
                  f"{status['parked_vehicles']} parked, "
                  f"total frames: {status['stats']['total_frames_processed']}")

    finally:
        db_pool.closeall()


if __name__ == "__main__":
    main()