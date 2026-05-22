# db/repository.py

import json
import numpy as np
import logging
from typing import List, Optional, Dict, Any, Tuple, Union
from psycopg2 import pool, sql, extensions
from psycopg2.extras import RealDictCursor
from psycopg2 import errors as psycopg2_errors
from datetime import datetime
from contextlib import contextmanager

from .models import Camera, SegmentsConfig, ParkingContainer, CameraCalibration

# Настройка логирования
logger = logging.getLogger(__name__)


class RepositoryError(Exception):
    """Базовое исключение для ошибок репозитория"""
    pass


class DatabaseConnectionError(RepositoryError):
    """Ошибка подключения к БД"""
    pass


class ValidationError(RepositoryError):
    """Ошибка валидации данных"""
    pass


class ParkingRepository:
    """
    Репозиторий для работы с базой данных парковки.
    Инкапсулирует все SQL запросы с обработкой ошибок и валидацией.
    """

    def __init__(self, connection_pool: pool.SimpleConnectionPool):
        self.pool = connection_pool
        logger.info("ParkingRepository initialized")

    @contextmanager
    def _get_connection(self):
        """Контекстный менеджер для получения и возврата соединения"""
        conn = None
        try:
            conn = self.pool.getconn()
            yield conn
        except Exception as e:
            logger.error(f"Error getting connection from pool: {e}")
            raise DatabaseConnectionError(f"Failed to get database connection: {e}")
        finally:
            if conn:
                self.pool.putconn(conn)

    @contextmanager
    def _transaction(self, conn):
        """Контекстный менеджер для транзакций"""
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Transaction failed, rolling back: {e}")
            raise

    # === Камеры ===

    def get_all_cameras(self) -> List[Camera]:
        """Получает все камеры"""
        with self._get_connection() as conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT id, video_path, name, location, segments_config_id, created_at
                        FROM cameras
                        ORDER BY id
                    """)
                    rows = cursor.fetchall()
                    return [Camera.from_db_row(dict(row)) for row in rows]
            except Exception as e:
                logger.error(f"Error getting all cameras: {e}", exc_info=True)
                raise RepositoryError(f"Failed to get cameras: {e}")

    def get_camera(self, camera_id: int) -> Optional[Camera]:
        """Получает камеру по ID"""
        if camera_id <= 0:
            raise ValidationError(f"Invalid camera_id: {camera_id}")

        with self._get_connection() as conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT id, video_path, name, location, segments_config_id, created_at
                        FROM cameras
                        WHERE id = %s
                    """, (camera_id,))
                    row = cursor.fetchone()
                    return Camera.from_db_row(dict(row)) if row else None
            except Exception as e:
                logger.error(f"Error getting camera {camera_id}: {e}", exc_info=True)
                raise RepositoryError(f"Failed to get camera {camera_id}: {e}")

    def add_camera(self, video_path: str, name: str, segments_config_id: int,
                   location: str = "") -> Camera:
        """Добавляет новую камеру"""
        # Валидация
        if not video_path:
            raise ValidationError("video_path cannot be empty")
        if not name or len(name) > 100:
            raise ValidationError("name must be between 1 and 100 characters")
        if segments_config_id <= 0:
            raise ValidationError(f"Invalid segments_config_id: {segments_config_id}")

        # Проверяем существование конфигурации сегментов
        config = self.get_segments_config(segments_config_id)
        if not config:
            raise ValidationError(f"Segments config with id {segments_config_id} not found")

        with self._get_connection() as conn:
            try:
                with self._transaction(conn):
                    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                        cursor.execute("""
                            INSERT INTO cameras (video_path, name, location, segments_config_id)
                            VALUES (%s, %s, %s, %s)
                            RETURNING id, video_path, name, location, segments_config_id, created_at
                        """, (video_path, name, location, segments_config_id))

                        row = cursor.fetchone()
                        if not row:
                            raise RepositoryError("Failed to insert camera - no row returned")

                        logger.info(f"Added camera with id {row['id']}")
                        return Camera.from_db_row(dict(row))

            except psycopg2_errors.UniqueViolation as e:
                logger.error(f"Duplicate camera name: {name}")
                raise ValidationError(f"Camera with name '{name}' already exists")
            except Exception as e:
                logger.error(f"Error adding camera: {e}", exc_info=True)
                raise RepositoryError(f"Failed to add camera: {e}")

    # === Конфигурации сегментов ===

    def get_all_segments_configs(self) -> List[SegmentsConfig]:
        """Получает все конфигурации сегментов"""
        with self._get_connection() as conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT id, name, horizontal_segments, vertical_segments, description, created_at
                        FROM segments_configs
                        ORDER BY name
                    """)
                    rows = cursor.fetchall()
                    return [SegmentsConfig.from_db_row(dict(row)) for row in rows]
            except Exception as e:
                logger.error(f"Error getting segments configs: {e}", exc_info=True)
                raise RepositoryError(f"Failed to get segments configs: {e}")

    def get_segments_config(self, config_id: int) -> Optional[SegmentsConfig]:
        """Получает конфигурацию сегментов по ID"""
        if config_id <= 0:
            raise ValidationError(f"Invalid config_id: {config_id}")

        with self._get_connection() as conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT id, name, horizontal_segments, vertical_segments, description, created_at
                        FROM segments_configs
                        WHERE id = %s
                    """, (config_id,))

                    row = cursor.fetchone()
                    return SegmentsConfig.from_db_row(dict(row)) if row else None
            except Exception as e:
                logger.error(f"Error getting segments config {config_id}: {e}", exc_info=True)
                raise RepositoryError(f"Failed to get segments config {config_id}: {e}")

    # === Парковочные контейнеры ===

    def get_camera_containers(self, camera_id: int) -> List[ParkingContainer]:
        """Получает все контейнеры для камеры"""
        if camera_id <= 0:
            raise ValidationError(f"Invalid camera_id: {camera_id}")

        with self._get_connection() as conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT id, camera_id, name, length, width, height,
                               ground_points, upper_points, image_points, is_base,
                               created_at, updated_at
                        FROM parking_containers
                        WHERE camera_id = %s
                        ORDER BY id
                    """, (camera_id,))

                    rows = cursor.fetchall()
                    containers = []
                    for row in rows:
                        try:
                            # Конвертируем в обычный dict для обработки
                            row_dict = dict(row)
                            containers.append(ParkingContainer.from_db_row(row_dict))
                        except Exception as e:
                            logger.error(f"Error parsing container row {row.get('id')}: {e}")
                            # Продолжаем с остальными контейнерами
                            continue

                    return containers
            except Exception as e:
                logger.error(f"Error getting containers for camera {camera_id}: {e}", exc_info=True)
                raise RepositoryError(f"Failed to get containers for camera {camera_id}: {e}")

    def get_container(self, container_id: int) -> Optional[ParkingContainer]:
        """Получает контейнер по ID"""
        if container_id <= 0:
            raise ValidationError(f"Invalid container_id: {container_id}")

        with self._get_connection() as conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT id, camera_id, name, length, width, height,
                               ground_points, upper_points, image_points, is_base,
                               created_at, updated_at
                        FROM parking_containers
                        WHERE id = %s
                    """, (container_id,))

                    row = cursor.fetchone()
                    if row:
                        return ParkingContainer.from_db_row(dict(row))
                    return None
            except Exception as e:
                logger.error(f"Error getting container {container_id}: {e}", exc_info=True)
                raise RepositoryError(f"Failed to get container {container_id}: {e}")

    def add_parking_container(self, camera_id: int, name: str,
                              length: float, width: float, height: float,
                              ground_points: List[Tuple[float, float, float]],
                              upper_points: List[Tuple[float, float, float]],
                              image_points: Optional[List[Tuple[float, float]]] = None,
                              is_base: bool = False) -> ParkingContainer:
        """Добавляет новый парковочный контейнер"""
        # Валидация
        if camera_id <= 0:
            raise ValidationError(f"Invalid camera_id: {camera_id}")

        if not name or len(name) > 100:
            raise ValidationError("name must be between 1 and 100 characters")

        if length <= 0 or width <= 0 or height <= 0:
            raise ValidationError(f"Dimensions must be positive: {length}x{width}x{height}")

        if len(ground_points) != 4:
            raise ValidationError(f"ground_points must have exactly 4 points, got {len(ground_points)}")

        if len(upper_points) != 4:
            raise ValidationError(f"upper_points must have exactly 4 points, got {len(upper_points)}")

        if image_points and len(image_points) != 4:
            raise ValidationError(f"image_points must have exactly 4 points if provided, got {len(image_points)}")

        # Проверяем существование камеры
        camera = self.get_camera(camera_id)
        if not camera:
            raise ValidationError(f"Camera with id {camera_id} does not exist")

        # Проверяем, не существует ли уже базовый контейнер для этой камеры
        if is_base:
            existing_containers = self.get_camera_containers(camera_id)
            if any(c.is_base for c in existing_containers):
                raise ValidationError(f"Camera {camera_id} already has a base container")

        with self._get_connection() as conn:
            try:
                with self._transaction(conn):
                    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                        # Сериализация точек в JSON
                        ground_json = json.dumps(ground_points)
                        upper_json = json.dumps(upper_points)
                        image_json = json.dumps(image_points) if image_points else None

                        cursor.execute("""
                            INSERT INTO parking_containers 
                            (camera_id, name, length, width, height, 
                             ground_points, upper_points, image_points, is_base,
                             created_at, updated_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                            RETURNING id, camera_id, name, length, width, height,
                                      ground_points, upper_points, image_points, is_base,
                                      created_at, updated_at
                        """, (camera_id, name, length, width, height,
                              ground_json, upper_json, image_json, is_base))

                        row = cursor.fetchone()
                        if not row:
                            raise RepositoryError("Failed to insert container - no row returned")

                        logger.info(f"Added container with id {row['id']} for camera {camera_id}")
                        return ParkingContainer.from_db_row(dict(row))

            except psycopg2_errors.UniqueViolation as e:
                logger.error(f"Duplicate container name '{name}' for camera {camera_id}")
                raise ValidationError(f"Container with name '{name}' already exists for this camera")
            except Exception as e:
                logger.error(f"Error adding container: {e}", exc_info=True)
                raise RepositoryError(f"Failed to add container: {e}")

    # === Калибровка камер ===

    def get_camera_data(self, container_id: int) -> Optional[CameraCalibration]:
        """Получает данные калибровки для контейнера (обычно для базового)"""
        if container_id <= 0:
            raise ValidationError(f"Invalid container_id: {container_id}")

        with self._get_connection() as conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT id, container_id, camera_matrix, rvec, tvec, dist_coeffs, image_shape, created_at
                        FROM camera_calibration
                        WHERE container_id = %s
                    """, (container_id,))

                    row = cursor.fetchone()
                    if row:
                        return CameraCalibration.from_db_row(dict(row))
                    return None
            except Exception as e:
                logger.error(f"Error getting calibration for container {container_id}: {e}", exc_info=True)
                raise RepositoryError(f"Failed to get calibration for container {container_id}: {e}")

    def add_camera_calibration(self, container_id: int,
                               camera_matrix: np.ndarray,
                               rvec: np.ndarray,
                               tvec: np.ndarray,
                               dist_coeffs: np.ndarray,
                               image_shape: Tuple[int, int]) -> CameraCalibration:
        """Добавляет данные калибровки"""
        # Валидация
        if container_id <= 0:
            raise ValidationError(f"Invalid container_id: {container_id}")

        if camera_matrix.shape != (3, 3):
            raise ValidationError(f"camera_matrix must be 3x3, got {camera_matrix.shape}")

        if len(image_shape) != 2 or image_shape[0] <= 0 or image_shape[1] <= 0:
            raise ValidationError(f"Invalid image_shape: {image_shape}")

        # Проверяем существование контейнера
        container = self.get_container(container_id)
        if not container:
            raise ValidationError(f"Container with id {container_id} does not exist")

        # Проверяем, не существует ли уже калибровка для этого контейнера
        existing = self.get_camera_data(container_id)
        if existing:
            raise ValidationError(f"Calibration already exists for container {container_id}")

        with self._get_connection() as conn:
            try:
                with self._transaction(conn):
                    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                        # Сериализация numpy массивов в JSON
                        camera_json = json.dumps(camera_matrix.tolist())
                        rvec_json = json.dumps(rvec.tolist())
                        tvec_json = json.dumps(tvec.tolist())
                        dist_json = json.dumps(dist_coeffs.tolist())
                        shape_json = json.dumps(image_shape)

                        cursor.execute("""
                            INSERT INTO camera_calibration 
                            (container_id, camera_matrix, rvec, tvec, dist_coeffs, image_shape, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, NOW())
                            RETURNING id, container_id, camera_matrix, rvec, tvec, dist_coeffs, image_shape, created_at
                        """, (container_id, camera_json, rvec_json, tvec_json, dist_json, shape_json))

                        row = cursor.fetchone()
                        if not row:
                            raise RepositoryError("Failed to insert calibration - no row returned")

                        logger.info(f"Added calibration for container {container_id}")
                        return CameraCalibration.from_db_row(dict(row))

            except Exception as e:
                logger.error(f"Error adding calibration: {e}", exc_info=True)
                raise RepositoryError(f"Failed to add calibration: {e}")

    # === Занятость мест ===

    def mark_spot_occupied(self, spot_id: int, vehicle_track_id: int) -> bool:
        """Отмечает место как занятое"""
        if spot_id <= 0 or vehicle_track_id <= 0:
            raise ValidationError(f"Invalid ids: spot_id={spot_id}, vehicle_track_id={vehicle_track_id}")

        with self._get_connection() as conn:
            try:
                with self._transaction(conn):
                    with conn.cursor() as cursor:
                        # Закрываем предыдущую запись, если есть
                        cursor.execute("""
                            UPDATE spot_occupancy 
                            SET occupied_until = NOW()
                            WHERE spot_id = %s AND occupied_until IS NULL
                        """, (spot_id,))

                        updated_count = cursor.rowcount

                        # Создаем новую
                        cursor.execute("""
                            INSERT INTO spot_occupancy (spot_id, vehicle_track_id, occupied_since)
                            VALUES (%s, %s, NOW())
                        """, (spot_id, vehicle_track_id))

                        logger.info(f"Marked spot {spot_id} as occupied by vehicle {vehicle_track_id}")
                        return True

            except psycopg2_errors.ForeignKeyViolation as e:
                logger.error(f"Invalid spot_id {spot_id} or vehicle_track_id {vehicle_track_id}")
                raise ValidationError(f"Invalid spot or vehicle track ID")
            except Exception as e:
                logger.error(f"Error marking spot {spot_id} as occupied: {e}", exc_info=True)
                return False

    def mark_spot_free(self, spot_id: int) -> bool:
        """Отмечает место как свободное"""
        if spot_id <= 0:
            raise ValidationError(f"Invalid spot_id: {spot_id}")

        with self._get_connection() as conn:
            try:
                with self._transaction(conn):
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            UPDATE spot_occupancy 
                            SET occupied_until = NOW()
                            WHERE spot_id = %s AND occupied_until IS NULL
                        """, (spot_id,))

                        freed_count = cursor.rowcount
                        if freed_count > 0:
                            logger.info(f"Marked spot {spot_id} as free")
                            return True
                        else:
                            logger.warning(f"Spot {spot_id} was not occupied")
                            return False

            except Exception as e:
                logger.error(f"Error marking spot {spot_id} as free: {e}", exc_info=True)
                return False

    def get_current_occupancy(self) -> Dict[int, int]:
        """Возвращает текущую занятость: {spot_id: vehicle_track_id}"""
        with self._get_connection() as conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT spot_id, vehicle_track_id
                        FROM spot_occupancy
                        WHERE occupied_until IS NULL
                    """)

                    return {row['spot_id']: row['vehicle_track_id'] for row in cursor.fetchall()}
            except Exception as e:
                logger.error(f"Error getting current occupancy: {e}", exc_info=True)
                raise RepositoryError(f"Failed to get current occupancy: {e}")

    # === Связи между камерами ===

    def get_all_camera_connections(self) -> List[Dict]:
        """Получает все связи между камерами"""
        with self._get_connection() as conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT 
                            id,
                            source_camera_id,
                            source_segment,
                            target_camera_id,
                            target_segment,
                            bidirectional,
                            weight,
                            metadata,
                            created_at
                        FROM camera_connections
                        ORDER BY source_camera_id, source_segment
                    """)

                    rows = cursor.fetchall()
                    return [self._parse_connection_row(dict(row)) for row in rows]
            except Exception as e:
                logger.error(f"Error getting all camera connections: {e}", exc_info=True)
                raise RepositoryError(f"Failed to get camera connections: {e}")

    def get_camera_connections(self, camera_id: int) -> List[Dict]:
        """Получает все связи для конкретной камеры"""
        if camera_id <= 0:
            raise ValidationError(f"Invalid camera_id: {camera_id}")

        with self._get_connection() as conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT 
                            id,
                            source_camera_id,
                            source_segment,
                            target_camera_id,
                            target_segment,
                            bidirectional,
                            weight,
                            metadata,
                            created_at
                        FROM camera_connections
                        WHERE source_camera_id = %s OR target_camera_id = %s
                        ORDER BY source_camera_id, source_segment
                    """, (camera_id, camera_id))

                    rows = cursor.fetchall()
                    return [self._parse_connection_row(dict(row)) for row in rows]
            except Exception as e:
                logger.error(f"Error getting connections for camera {camera_id}: {e}", exc_info=True)
                raise RepositoryError(f"Failed to get connections for camera {camera_id}: {e}")

    def add_camera_connection(self,
                              source_camera_id: int,
                              source_segment: str,
                              target_camera_id: int,
                              target_segment: str,
                              bidirectional: bool = True,
                              weight: float = 1.0,
                              metadata: Optional[Dict] = None) -> Optional[int]:
        """Добавляет связь между камерами"""
        # Валидация
        if source_camera_id <= 0 or target_camera_id <= 0:
            raise ValidationError(f"Invalid camera ids: {source_camera_id}, {target_camera_id}")

        if not source_segment or not target_segment:
            raise ValidationError("Segment names cannot be empty")

        if weight <= 0:
            raise ValidationError(f"Weight must be positive, got {weight}")

        if source_camera_id == target_camera_id:
            raise ValidationError("Source and target cameras must be different")

        # Проверяем существование камер
        source_camera = self.get_camera(source_camera_id)
        if not source_camera:
            raise ValidationError(f"Source camera {source_camera_id} does not exist")

        target_camera = self.get_camera(target_camera_id)
        if not target_camera:
            raise ValidationError(f"Target camera {target_camera_id} does not exist")

        with self._get_connection() as conn:
            try:
                with self._transaction(conn):
                    with conn.cursor() as cursor:
                        metadata_json = json.dumps(metadata) if metadata else None

                        cursor.execute("""
                            INSERT INTO camera_connections 
                            (source_camera_id, source_segment, target_camera_id, target_segment, 
                             bidirectional, weight, metadata, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
                            ON CONFLICT (source_camera_id, source_segment, target_camera_id, target_segment) 
                            DO UPDATE SET
                                bidirectional = EXCLUDED.bidirectional,
                                weight = EXCLUDED.weight,
                                metadata = EXCLUDED.metadata
                            RETURNING id
                        """, (source_camera_id, source_segment, target_camera_id, target_segment,
                              bidirectional, weight, metadata_json))

                        result = cursor.fetchone()
                        connection_id = result[0] if result else None

                        if connection_id:
                            logger.info(f"Added/updated camera connection with id {connection_id}")
                        return connection_id

            except psycopg2_errors.ForeignKeyViolation as e:
                logger.error(f"Invalid camera ID in connection: {e}")
                raise ValidationError("One or both camera IDs are invalid")
            except Exception as e:
                logger.error(f"Error adding camera connection: {e}", exc_info=True)
                return None

    def remove_camera_connection(self, connection_id: int) -> bool:
        """Удаляет связь по ID"""
        if connection_id <= 0:
            raise ValidationError(f"Invalid connection_id: {connection_id}")

        with self._get_connection() as conn:
            try:
                with self._transaction(conn):
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            DELETE FROM camera_connections
                            WHERE id = %s
                        """, (connection_id,))

                        deleted = cursor.rowcount > 0
                        if deleted:
                            logger.info(f"Removed camera connection {connection_id}")
                        return deleted

            except Exception as e:
                logger.error(f"Error removing camera connection {connection_id}: {e}", exc_info=True)
                return False

    def remove_camera_connections_by_camera(self, camera_id: int) -> int:
        """Удаляет все связи с участием камеры"""
        if camera_id <= 0:
            raise ValidationError(f"Invalid camera_id: {camera_id}")

        with self._get_connection() as conn:
            try:
                with self._transaction(conn):
                    with conn.cursor() as cursor:
                        cursor.execute("""
                            DELETE FROM camera_connections
                            WHERE source_camera_id = %s OR target_camera_id = %s
                        """, (camera_id, camera_id))

                        deleted_count = cursor.rowcount
                        if deleted_count > 0:
                            logger.info(f"Removed {deleted_count} connections for camera {camera_id}")
                        return deleted_count

            except Exception as e:
                logger.error(f"Error removing connections for camera {camera_id}: {e}", exc_info=True)
                return 0

    # === Вспомогательные методы ===

    @staticmethod
    def _parse_connection_row(row: dict) -> dict:
        """Парсит строку связи, конвертируя JSON поля"""
        if 'metadata' in row and row['metadata']:
            if isinstance(row['metadata'], str):
                try:
                    row['metadata'] = json.loads(row['metadata'])
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse metadata JSON: {row['metadata']}")
                    row['metadata'] = None

        # Конвертируем datetime в строку для JSON сериализации
        if 'created_at' in row and row['created_at']:
            if hasattr(row['created_at'], 'isoformat'):
                row['created_at'] = row['created_at'].isoformat()

        return row

    def health_check(self) -> bool:
        """Проверяет соединение с БД"""
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False