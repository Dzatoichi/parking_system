import json
import logging
from typing import List, Optional, Dict, Any, Tuple, Union
from datetime import datetime
from contextlib import contextmanager

import numpy as np
import psycopg2
from psycopg2 import pool, sql
from psycopg2.extras import RealDictCursor
from psycopg2 import errors as psycopg2_errors

from parking_monitor.db.models import (
    Camera, SegmentsConfig, ParkingContainer, CameraCalibration,
    CameraConnection, OccupancyRecord
)

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


class NotFoundError(RepositoryError):
    """Объект не найден"""
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
            if conn:
                try:
                    conn.rollback()
                except Exception:
                    pass
            logger.error(f"Error with database connection: {e}")
            raise DatabaseConnectionError(f"Database operation failed: {e}")
        finally:
            if conn:
                try:
                    self.pool.putconn(conn)
                except Exception as e:
                    logger.error(f"Error returning connection to pool: {e}")

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

    def get_all_cameras(self, limit: int = 100, offset: int = 0) -> List[Camera]:
        """Получает все камеры с пагинацией"""
        if limit <= 0 or limit > 1000:
            raise ValidationError(f"Limit must be between 1 and 1000, got {limit}")
        if offset < 0:
            raise ValidationError(f"Offset must be non-negative, got {offset}")

        with self._get_connection() as conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT id, video_path, name, location, segments_config_id, is_active, created_at, updated_at
                        FROM cameras
                        ORDER BY id
                        LIMIT %s OFFSET %s
                    """, (limit, offset))
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
                        SELECT id, video_path, name, location, segments_config_id, is_active, created_at, updated_at
                        FROM cameras
                        WHERE id = %s
                    """, (camera_id,))
                    row = cursor.fetchone()
                    return Camera.from_db_row(dict(row)) if row else None
            except Exception as e:
                logger.error(f"Error getting camera {camera_id}: {e}", exc_info=True)
                raise RepositoryError(f"Failed to get camera {camera_id}: {e}")

    def get_camera_by_name(self, name: str) -> Optional[Camera]:
        """Получает камеру по имени"""
        if not name:
            raise ValidationError("Name cannot be empty")

        with self._get_connection() as conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT id, video_path, name, location, segments_config_id, is_active, created_at, updated_at
                        FROM cameras
                        WHERE name = %s
                    """, (name,))
                    row = cursor.fetchone()
                    return Camera.from_db_row(dict(row)) if row else None
            except Exception as e:
                logger.error(f"Error getting camera by name {name}: {e}", exc_info=True)
                raise RepositoryError(f"Failed to get camera by name: {e}")

    def add_camera(self, video_path: str, name: str, segments_config_id: int,
                   location: str = "", is_active: bool = True) -> Camera:
        """Добавляет новую камеру"""
        self._validate_camera_input(video_path, name, segments_config_id)

        # Проверяем существование конфигурации сегментов
        config = self.get_segments_config(segments_config_id)
        if not config:
            raise ValidationError(f"Segments config with id {segments_config_id} not found")

        # Проверяем уникальность имени
        existing = self.get_camera_by_name(name)
        if existing:
            raise ValidationError(f"Camera with name '{name}' already exists")

        with self._get_connection() as conn:
            try:
                with self._transaction(conn):
                    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                        cursor.execute("""
                            INSERT INTO cameras (video_path, name, location, segments_config_id, is_active)
                            VALUES (%s, %s, %s, %s, %s)
                            RETURNING id, video_path, name, location, segments_config_id, is_active, created_at, updated_at
                        """, (video_path, name, location, segments_config_id, is_active))

                        row = cursor.fetchone()
                        if not row:
                            raise RepositoryError("Failed to insert camera - no row returned")

                        logger.info(f"Added camera with id {row['id']}")
                        return Camera.from_db_row(dict(row))

            except Exception as e:
                logger.error(f"Error adding camera: {e}", exc_info=True)
                raise RepositoryError(f"Failed to add camera: {e}")

    def update_camera(self, camera_id: int, **kwargs) -> Camera:
        """Обновляет данные камеры"""
        if camera_id <= 0:
            raise ValidationError(f"Invalid camera_id: {camera_id}")

        # Проверяем существование
        existing = self.get_camera(camera_id)
        if not existing:
            raise NotFoundError(f"Camera with id {camera_id} not found")

        # Валидация обновляемых полей
        allowed_fields = {'video_path', 'name', 'location', 'segments_config_id', 'is_active'}
        update_fields = []
        values = []

        for field, value in kwargs.items():
            if field not in allowed_fields:
                raise ValidationError(f"Invalid field for update: {field}")

            if field == 'name' and value:
                # Проверяем уникальность имени при смене
                existing_by_name = self.get_camera_by_name(value)
                if existing_by_name and existing_by_name.id != camera_id:
                    raise ValidationError(f"Camera with name '{value}' already exists")
                update_fields.append(f"{field} = %s")
                values.append(value)

            elif field == 'segments_config_id' and value:
                config = self.get_segments_config(value)
                if not config:
                    raise ValidationError(f"Segments config with id {value} not found")
                update_fields.append(f"{field} = %s")
                values.append(value)

            elif value is not None:
                update_fields.append(f"{field} = %s")
                values.append(value)

        if not update_fields:
            return existing

        values.append(camera_id)
        update_query = f"UPDATE cameras SET {', '.join(update_fields)}, updated_at = NOW() WHERE id = %s RETURNING *"

        with self._get_connection() as conn:
            try:
                with self._transaction(conn):
                    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                        cursor.execute(update_query, values)
                        row = cursor.fetchone()
                        if not row:
                            raise RepositoryError("Failed to update camera")

                        logger.info(f"Updated camera with id {camera_id}")
                        return Camera.from_db_row(dict(row))

            except Exception as e:
                logger.error(f"Error updating camera {camera_id}: {e}", exc_info=True)
                raise RepositoryError(f"Failed to update camera: {e}")

    def delete_camera(self, camera_id: int) -> bool:
        """Удаляет камеру"""
        if camera_id <= 0:
            raise ValidationError(f"Invalid camera_id: {camera_id}")

        with self._get_connection() as conn:
            try:
                with self._transaction(conn):
                    with conn.cursor() as cursor:
                        cursor.execute("DELETE FROM cameras WHERE id = %s", (camera_id,))
                        deleted = cursor.rowcount > 0
                        if deleted:
                            logger.info(f"Deleted camera with id {camera_id}")
                        return deleted

            except psycopg2_errors.ForeignKeyViolation as e:
                logger.error(f"Cannot delete camera {camera_id} - has dependent records")
                raise ValidationError(f"Cannot delete camera: it has dependent records")
            except Exception as e:
                logger.error(f"Error deleting camera {camera_id}: {e}", exc_info=True)
                raise RepositoryError(f"Failed to delete camera: {e}")

    def _validate_camera_input(self, video_path: str, name: str, segments_config_id: int):
        """Валидирует входные данные для камеры"""
        if not video_path:
            raise ValidationError("video_path cannot be empty")
        if not name or len(name) > 100:
            raise ValidationError("name must be between 1 and 100 characters")
        if segments_config_id <= 0:
            raise ValidationError(f"Invalid segments_config_id: {segments_config_id}")

    # === Конфигурации сегментов ===

    def get_all_segments_configs(self, limit: int = 100, offset: int = 0) -> List[SegmentsConfig]:
        """Получает все конфигурации сегментов"""
        with self._get_connection() as conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT id, name, horizontal_segments, vertical_segments, description, created_at
                        FROM segments_configs
                        ORDER BY name
                        LIMIT %s OFFSET %s
                    """, (limit, offset))
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

    def add_segments_config(self, name: str, horizontal_segments: int,
                           vertical_segments: int, description: Optional[str] = None) -> SegmentsConfig:
        """Добавляет новую конфигурацию сегментов"""
        if not name or len(name) > 100:
            raise ValidationError("name must be between 1 and 100 characters")
        if horizontal_segments <= 0 or horizontal_segments > 20:
            raise ValidationError(f"horizontal_segments must be between 1 and 20, got {horizontal_segments}")
        if vertical_segments <= 0 or vertical_segments > 20:
            raise ValidationError(f"vertical_segments must be between 1 and 20, got {vertical_segments}")

        with self._get_connection() as conn:
            try:
                with self._transaction(conn):
                    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                        cursor.execute("""
                            INSERT INTO segments_configs (name, horizontal_segments, vertical_segments, description)
                            VALUES (%s, %s, %s, %s)
                            RETURNING id, name, horizontal_segments, vertical_segments, description, created_at
                        """, (name, horizontal_segments, vertical_segments, description))

                        row = cursor.fetchone()
                        if not row:
                            raise RepositoryError("Failed to insert segments config")

                        logger.info(f"Added segments config with id {row['id']}")
                        return SegmentsConfig.from_db_row(dict(row))

            except psycopg2_errors.UniqueViolation:
                raise ValidationError(f"Segments config with name '{name}' already exists")
            except Exception as e:
                logger.error(f"Error adding segments config: {e}", exc_info=True)
                raise RepositoryError(f"Failed to add segments config: {e}")

    # === Парковочные контейнеры ===

    def get_camera_containers(self, camera_id: int) -> List[ParkingContainer]:
        """Получает все контейнеры для камеры"""
        if camera_id <= 0:
            raise ValidationError(f"Invalid camera_id: {camera_id}")

        with self._get_connection() as conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT id, camera_id, spot_id, name, length, width, height,
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
                            containers.append(ParkingContainer.from_db_row(dict(row)))
                        except Exception as e:
                            logger.error(f"Error parsing container row {row.get('id')}: {e}")
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
                        SELECT id, camera_id, spot_id, name, length, width, height,
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

    def get_base_container(self, camera_id: int) -> Optional[ParkingContainer]:
        """Получает базовый контейнер для камеры"""
        if camera_id <= 0:
            raise ValidationError(f"Invalid camera_id: {camera_id}")

        with self._get_connection() as conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT id, camera_id, spot_id, name, length, width, height,
                               ground_points, upper_points, image_points, is_base,
                               created_at, updated_at
                        FROM parking_containers
                        WHERE camera_id = %s AND is_base = true
                    """, (camera_id,))

                    row = cursor.fetchone()
                    if row:
                        return ParkingContainer.from_db_row(dict(row))
                    return None
            except Exception as e:
                logger.error(f"Error getting base container for camera {camera_id}: {e}", exc_info=True)
                raise RepositoryError(f"Failed to get base container: {e}")

    def add_parking_container(self, camera_id: int, name: str,
                              length: float, width: float, height: float,
                              ground_points: np.ndarray,
                              upper_points: np.ndarray,
                              image_points: Optional[np.ndarray] = None,
                              is_base: bool = False) -> ParkingContainer:
        """Добавляет новый парковочный контейнер"""
        # Валидация через модели
        temp_container = ParkingContainer(
            id=-1,  # временный ID
            camera_id=camera_id,
            name=name,
            length=length,
            width=width,
            height=height,
            ground_points=ground_points,
            upper_points=upper_points,
            image_points=image_points,
            is_base=is_base
        )

        # Проверяем существование камеры
        camera = self.get_camera(camera_id)
        if not camera:
            raise ValidationError(f"Camera with id {camera_id} does not exist")

        # Проверяем, не существует ли уже базовый контейнер для этой камеры
        if is_base:
            existing_base = self.get_base_container(camera_id)
            if existing_base:
                raise ValidationError(f"Camera {camera_id} already has a base container")

        with self._get_connection() as conn:
            try:
                with self._transaction(conn):
                    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                        # Конвертируем numpy в JSONB
                        ground_json = json.dumps(ground_points.tolist())
                        upper_json = json.dumps(upper_points.tolist())
                        image_json = json.dumps(image_points.tolist()) if image_points is not None else None

                        cursor.execute("""
                            INSERT INTO parking_containers 
                            (camera_id, name, length, width, height, 
                             ground_points, upper_points, image_points, is_base)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            RETURNING id, camera_id, name, length, width, height,
                                      ground_points, upper_points, image_points, is_base,
                                      created_at, updated_at
                        """, (camera_id, name, length, width, height,
                              ground_json, upper_json, image_json, is_base))

                        row = cursor.fetchone()
                        if not row:
                            raise RepositoryError("Failed to insert container")

                        logger.info(f"Added container with id {row['id']} for camera {camera_id}")
                        return ParkingContainer.from_db_row(dict(row))

            except psycopg2_errors.UniqueViolation:
                raise ValidationError(f"Container with name '{name}' already exists for this camera")
            except Exception as e:
                logger.error(f"Error adding container: {e}", exc_info=True)
                raise RepositoryError(f"Failed to add container: {e}")

    def update_parking_container(self, container_id: int, **kwargs) -> ParkingContainer:
        """Обновляет данные парковочного контейнера"""
        if container_id <= 0:
            raise ValidationError(f"Invalid container_id: {container_id}")

        existing = self.get_container(container_id)
        if not existing:
            raise NotFoundError(f"Container with id {container_id} not found")

        allowed_fields = {'name', 'length', 'width', 'height', 'ground_points', 'upper_points', 'image_points',
                          'is_base'}
        update_fields = []
        values = []

        for field, value in kwargs.items():
            if field not in allowed_fields:
                raise ValidationError(f"Invalid field for update: {field}")

            if field in ('ground_points', 'upper_points', 'image_points'):
                if value is not None:
                    # Конвертируем numpy в JSONB
                    if isinstance(value, np.ndarray):
                        value = json.dumps(value.tolist())
                    else:
                        value = json.dumps(value)
                update_fields.append(f"{field} = %s")
                values.append(value)
            elif value is not None:
                update_fields.append(f"{field} = %s")
                values.append(value)

        if not update_fields:
            return existing

        values.append(container_id)
        update_query = f"UPDATE parking_containers SET {', '.join(update_fields)}, updated_at = NOW() WHERE id = %s RETURNING *"

        with self._get_connection() as conn:
            try:
                with self._transaction(conn):
                    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                        cursor.execute(update_query, values)
                        row = cursor.fetchone()
                        if not row:
                            raise RepositoryError("Failed to update container")

                        logger.info(f"Updated container with id {container_id}")
                        return ParkingContainer.from_db_row(dict(row))

            except Exception as e:
                logger.error(f"Error updating container {container_id}: {e}", exc_info=True)
                raise RepositoryError(f"Failed to update container: {e}")

    def delete_parking_container(self, container_id: int) -> bool:
        """Удаляет парковочный контейнер"""
        if container_id <= 0:
            raise ValidationError(f"Invalid container_id: {container_id}")

        with self._get_connection() as conn:
            try:
                with self._transaction(conn):
                    with conn.cursor() as cursor:
                        cursor.execute("DELETE FROM parking_containers WHERE id = %s", (container_id,))
                        deleted = cursor.rowcount > 0
                        if deleted:
                            logger.info(f"Deleted container with id {container_id}")
                        return deleted

            except psycopg2_errors.ForeignKeyViolation as e:
                logger.error(f"Cannot delete container {container_id} - has dependent records")
                raise ValidationError(f"Cannot delete container: it has dependent records")
            except Exception as e:
                logger.error(f"Error deleting container {container_id}: {e}", exc_info=True)
                raise RepositoryError(f"Failed to delete container: {e}")

    def _validate_container_input(self, camera_id: int, name: str,
                                   length: float, width: float, height: float,
                                   ground_points: List[List[float]],
                                   upper_points: List[List[float]],
                                   image_points: Optional[List[List[float]]] = None):
        """Валидирует входные данные для контейнера"""
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

        # Проверка размерности точек
        for points in [ground_points, upper_points]:
            for i, point in enumerate(points):
                if len(point) != 3:
                    raise ValidationError(f"Point {i} must have 3 coordinates, got {len(point)}")

        if image_points:
            for i, point in enumerate(image_points):
                if len(point) != 2:
                    raise ValidationError(f"Image point {i} must have 2 coordinates, got {len(point)}")

    # === Калибровка камер ===

    def get_camera_calibration(self, container_id: int) -> Optional[CameraCalibration]:
        """Получает данные калибровки для контейнера"""
        if container_id <= 0:
            raise ValidationError(f"Invalid container_id: {container_id}")

        with self._get_connection() as conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT id, container_id, camera_matrix, rvec, tvec, dist_coeffs, image_shape, homography, created_at
                        FROM camera_calibrations
                        WHERE container_id = %s
                    """, (container_id,))
                    row = cursor.fetchone()
                    if row:
                        return CameraCalibration.from_db_row(dict(row))
                    return None
            except Exception as e:
                logger.error(f"Error getting calibration for container {container_id}: {e}", exc_info=True)
                raise RepositoryError(f"Failed to get calibration: {e}")

    def add_camera_calibration(self, container_id: int,
                               camera_matrix: np.ndarray,
                               rvec: np.ndarray,
                               tvec: np.ndarray,
                               dist_coeffs: np.ndarray,
                               image_shape: Tuple[int, int],
                               homography: Optional[np.ndarray] = None) -> CameraCalibration:
        """Добавляет данные калибровки"""
        # Валидация через модели
        temp_calib = CameraCalibration(
            id=-1,
            container_id=container_id,
            camera_matrix=camera_matrix,
            rvec=rvec,
            tvec=tvec,
            dist_coeffs=dist_coeffs,
            image_shape=image_shape
        )

        # Проверяем существование контейнера
        container = self.get_container(container_id)
        if not container:
            raise ValidationError(f"Container with id {container_id} does not exist")

        # Проверяем, не существует ли уже калибровка для этого контейнера
        existing = self.get_camera_calibration(container_id)
        if existing:
            raise ValidationError(f"Calibration already exists for container {container_id}")

        with self._get_connection() as conn:
            try:
                with self._transaction(conn):
                    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                        # Конвертируем numpy в JSONB
                        camera_json = json.dumps(camera_matrix.tolist())
                        rvec_json = json.dumps(rvec.tolist())
                        tvec_json = json.dumps(tvec.tolist())
                        dist_json = json.dumps(dist_coeffs.tolist())
                        shape_json = json.dumps(list(image_shape))
                        homography_json = json.dumps(homography.tolist()) if homography is not None else None

                        cursor.execute("""
                            INSERT INTO camera_calibrations
                            (container_id, camera_matrix, rvec, tvec, dist_coeffs, image_shape, homography)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            RETURNING id, container_id, camera_matrix, rvec, tvec, dist_coeffs, image_shape, homography, 
                            created_at
                        """, (container_id, camera_json, rvec_json, tvec_json, dist_json, shape_json, homography_json))

                        row = cursor.fetchone()
                        if not row:
                            raise RepositoryError("Failed to insert calibration")

                        logger.info(f"Added calibration for container {container_id}")
                        return CameraCalibration.from_db_row(dict(row))

            except Exception as e:
                logger.error(f"Error adding calibration: {e}", exc_info=True)
                raise RepositoryError(f"Failed to add calibration: {e}")

    def update_camera_calibration(self, container_id: int, **kwargs) -> CameraCalibration:
        """Обновляет данные калибровки"""
        if container_id <= 0:
            raise ValidationError(f"Invalid container_id: {container_id}")

        existing = self.get_camera_calibration(container_id)
        if not existing:
            raise NotFoundError(f"Calibration for container {container_id} not found")

        allowed_fields = {'camera_matrix', 'rvec', 'tvec', 'dist_coeffs', 'image_shape', 'homography'}
        update_fields = []
        values = []

        for field, value in kwargs.items():
            if field not in allowed_fields:
                raise ValidationError(f"Invalid field for update: {field}")

            if field == 'image_shape':
                value = json.dumps(list(value))
            elif field == 'homography' and value is not None:
                if isinstance(value, np.ndarray):
                    value = json.dumps(value.tolist())
                else:
                    value = json.dumps(value)
            elif isinstance(value, np.ndarray):
                value = json.dumps(value.tolist())
            elif value is not None:
                value = json.dumps(value)

            update_fields.append(f"{field} = %s")
            values.append(value)

        if not update_fields:
            return existing

        values.append(container_id)
        update_query = f"UPDATE camera_calibrations SET {', '.join(update_fields)} WHERE container_id = %s RETURNING *"

        with self._get_connection() as conn:
            try:
                with self._transaction(conn):
                    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                        cursor.execute(update_query, values)
                        row = cursor.fetchone()
                        if not row:
                            raise RepositoryError("Failed to update calibration")

                        logger.info(f"Updated calibration for container {container_id}")
                        return CameraCalibration.from_db_row(dict(row))

            except Exception as e:
                logger.error(f"Error updating calibration for container {container_id}: {e}", exc_info=True)
                raise RepositoryError(f"Failed to update calibration: {e}")

    def delete_camera_calibration(self, container_id: int) -> bool:
        """Удаляет данные калибровки"""
        if container_id <= 0:
            raise ValidationError(f"Invalid container_id: {container_id}")

        with self._get_connection() as conn:
            try:
                with self._transaction(conn):
                    with conn.cursor() as cursor:
                        cursor.execute("DELETE FROM camera_calibrations WHERE container_id = %s", (container_id,))
                        deleted = cursor.rowcount > 0
                        if deleted:
                            logger.info(f"Deleted calibration for container {container_id}")
                        return deleted

            except Exception as e:
                logger.error(f"Error deleting calibration for container {container_id}: {e}", exc_info=True)
                raise RepositoryError(f"Failed to delete calibration: {e}")

    def _validate_calibration_input(self, container_id: int,
                                     camera_matrix: List[List[float]],
                                     rvec: List[float],
                                     tvec: List[float],
                                     dist_coeffs: List[float],
                                     image_shape: Tuple[int, int]):
        """Валидирует входные данные для калибровки"""
        if container_id <= 0:
            raise ValidationError(f"Invalid container_id: {container_id}")
        if len(camera_matrix) != 3 or any(len(row) != 3 for row in camera_matrix):
            raise ValidationError(f"camera_matrix must be 3x3, got {camera_matrix}")
        if len(rvec) != 3:
            raise ValidationError(f"rvec must have 3 elements, got {len(rvec)}")
        if len(tvec) != 3:
            raise ValidationError(f"tvec must have 3 elements, got {len(tvec)}")
        if len(image_shape) != 2 or image_shape[0] <= 0 or image_shape[1] <= 0:
            raise ValidationError(f"Invalid image_shape: {image_shape}")

    # === Занятость мест ===

    def mark_spot_occupied(self, spot_id: int, vehicle_track_id: int) -> OccupancyRecord:
        """Отмечает место как занятое"""
        if spot_id <= 0:
            raise ValidationError(f"Invalid spot_id: {spot_id}")
        if vehicle_track_id <= 0:
            raise ValidationError(f"Invalid vehicle_track_id: {vehicle_track_id}")

        # Проверяем существование места
        container = self.get_container(spot_id)
        if not container:
            raise ValidationError(f"Spot with id {spot_id} does not exist")

        with self._get_connection() as conn:
            try:
                with self._transaction(conn):
                    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                        # Закрываем предыдущую запись, если есть
                        cursor.execute("""
                            UPDATE spot_occupancy 
                            SET occupied_until = NOW()
                            WHERE spot_id = %s AND occupied_until IS NULL
                            RETURNING *
                        """, (spot_id,))

                        # Создаем новую
                        cursor.execute("""
                            INSERT INTO spot_occupancy (spot_id, vehicle_track_id, occupied_since)
                            VALUES (%s, %s, NOW())
                            RETURNING spot_id, vehicle_track_id, occupied_since, occupied_until
                        """, (spot_id, vehicle_track_id))

                        row = cursor.fetchone()
                        if not row:
                            raise RepositoryError("Failed to mark spot as occupied")

                        logger.info(f"Marked spot {spot_id} as occupied by vehicle {vehicle_track_id}")
                        return OccupancyRecord.from_db_row(dict(row))

            except Exception as e:
                logger.error(f"Error marking spot {spot_id} as occupied: {e}", exc_info=True)
                raise RepositoryError(f"Failed to mark spot as occupied: {e}")

    def mark_spot_free(self, spot_id: int) -> Optional[OccupancyRecord]:
        """Отмечает место как свободное"""
        if spot_id <= 0:
            raise ValidationError(f"Invalid spot_id: {spot_id}")

        with self._get_connection() as conn:
            try:
                with self._transaction(conn):
                    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                        cursor.execute("""
                            UPDATE spot_occupancy 
                            SET occupied_until = NOW()
                            WHERE spot_id = %s AND occupied_until IS NULL
                            RETURNING spot_id, vehicle_track_id, occupied_since, occupied_until
                        """, (spot_id,))

                        row = cursor.fetchone()
                        if row:
                            logger.info(f"Marked spot {spot_id} as free")
                            return OccupancyRecord.from_db_row(dict(row))
                        else:
                            logger.warning(f"Spot {spot_id} was not occupied")
                            return None

            except Exception as e:
                logger.error(f"Error marking spot {spot_id} as free: {e}", exc_info=True)
                raise RepositoryError(f"Failed to mark spot as free: {e}")

    def update_current_spot(self, spot_id: int, status: str,
                            vehicle_track_id: Optional[int] = None,
                            parked_since: Optional[datetime] = None):
        """Обновляет текущее состояние места в БД"""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO parking_spots_current (spot_id, status, vehicle_track_id, parked_since, last_updated)
                    VALUES (%s, %s, %s, %s, NOW())
                    ON CONFLICT (spot_id) DO UPDATE SET
                        status = EXCLUDED.status,
                        vehicle_track_id = EXCLUDED.vehicle_track_id,
                        parked_since = EXCLUDED.parked_since,
                        last_updated = NOW()
                """, (spot_id, status, vehicle_track_id, parked_since))
                conn.commit()

    def initialize_all_spots(self):
        """Гарантирует, что для каждого parking_containers есть запись в parking_spots_current"""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO parking_spots_current (spot_id, status)
                    SELECT id, 'free'
                    FROM parking_containers
                    ON CONFLICT (spot_id) DO NOTHING
                """)
                conn.commit()

    def get_current_spot_statuses(self) -> Dict[int, Tuple[str, Optional[int], Optional[datetime]]]:
        """Возвращает {spot_id: (status, vehicle_track_id, parked_since)} для инициализации"""
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT spot_id, status, vehicle_track_id, parked_since FROM parking_spots_current")
                rows = cur.fetchall()
                return {
                    row['spot_id']: (row['status'], row['vehicle_track_id'], row['parked_since'])
                    for row in rows
                }

    def get_current_occupancy(self) -> List[OccupancyRecord]:
        """Возвращает текущую занятость"""
        with self._get_connection() as conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT spot_id, vehicle_track_id, occupied_since, occupied_until
                        FROM spot_occupancy
                        WHERE occupied_until IS NULL
                    """)

                    rows = cursor.fetchall()
                    return [OccupancyRecord.from_db_row(dict(row)) for row in rows]

            except Exception as e:
                logger.error(f"Error getting current occupancy: {e}", exc_info=True)
                raise RepositoryError(f"Failed to get current occupancy: {e}")

    def get_spot_occupancy_history(self, spot_id: int, limit: int = 100) -> List[OccupancyRecord]:
        """Получает историю занятости места"""
        if spot_id <= 0:
            raise ValidationError(f"Invalid spot_id: {spot_id}")
        if limit <= 0 or limit > 1000:
            raise ValidationError(f"Limit must be between 1 and 1000, got {limit}")

        with self._get_connection() as conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT spot_id, vehicle_track_id, occupied_since, occupied_until
                        FROM spot_occupancy
                        WHERE spot_id = %s
                        ORDER BY occupied_since DESC
                        LIMIT %s
                    """, (spot_id, limit))

                    rows = cursor.fetchall()
                    return [OccupancyRecord.from_db_row(dict(row)) for row in rows]

            except Exception as e:
                logger.error(f"Error getting occupancy history for spot {spot_id}: {e}", exc_info=True)
                raise RepositoryError(f"Failed to get occupancy history: {e}")

    # === Связи между камерами ===

    def get_all_camera_connections(self, limit: int = 100, offset: int = 0) -> List[CameraConnection]:
        """Получает все связи между камерами"""
        with self._get_connection() as conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT id, source_camera_id, source_segment, target_camera_id, target_segment,
                               bidirectional, weight, metadata, created_at
                        FROM camera_connections
                        ORDER BY source_camera_id, source_segment
                        LIMIT %s OFFSET %s
                    """, (limit, offset))

                    rows = cursor.fetchall()
                    return [CameraConnection.from_db_row(dict(row)) for row in rows]

            except Exception as e:
                logger.error(f"Error getting camera connections: {e}", exc_info=True)
                raise RepositoryError(f"Failed to get camera connections: {e}")

    def get_camera_connections(self, camera_id: int) -> List[CameraConnection]:
        """Получает все связи для конкретной камеры"""
        if camera_id <= 0:
            raise ValidationError(f"Invalid camera_id: {camera_id}")

        with self._get_connection() as conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT id, source_camera_id, source_segment, target_camera_id, target_segment,
                               bidirectional, weight, metadata, created_at
                        FROM camera_connections
                        WHERE source_camera_id = %s OR target_camera_id = %s
                        ORDER BY source_camera_id, source_segment
                    """, (camera_id, camera_id))

                    rows = cursor.fetchall()
                    return [CameraConnection.from_db_row(dict(row)) for row in rows]

            except Exception as e:
                logger.error(f"Error getting connections for camera {camera_id}: {e}", exc_info=True)
                raise RepositoryError(f"Failed to get connections for camera: {e}")

    def add_camera_connection(self,
                              source_camera_id: int,
                              source_segment: str,
                              target_camera_id: int,
                              target_segment: str,
                              bidirectional: bool = True,
                              weight: float = 1.0,
                              metadata: Optional[Dict[str, Any]] = None) -> CameraConnection:
        """Добавляет связь между камерами"""
        self._validate_connection_input(source_camera_id, source_segment,
                                        target_camera_id, target_segment, weight)

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
                    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                        metadata_json = json.dumps(metadata) if metadata else None

                        cursor.execute("""
                            INSERT INTO camera_connections 
                            (source_camera_id, source_segment, target_camera_id, target_segment, 
                             bidirectional, weight, metadata)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            ON CONFLICT (source_camera_id, source_segment, target_camera_id, target_segment) 
                            DO UPDATE SET
                                bidirectional = EXCLUDED.bidirectional,
                                weight = EXCLUDED.weight,
                                metadata = EXCLUDED.metadata
                            RETURNING id, source_camera_id, source_segment, target_camera_id, target_segment,
                                      bidirectional, weight, metadata, created_at
                        """, (source_camera_id, source_segment, target_camera_id, target_segment,
                              bidirectional, weight, metadata_json))

                        row = cursor.fetchone()
                        if not row:
                            raise RepositoryError("Failed to insert camera connection")

                        logger.info(f"Added/updated camera connection between {source_camera_id}:{source_segment} "
                                   f"and {target_camera_id}:{target_segment}")
                        return CameraConnection.from_db_row(dict(row))

            except Exception as e:
                logger.error(f"Error adding camera connection: {e}", exc_info=True)
                raise RepositoryError(f"Failed to add camera connection: {e}")

    def update_camera_connection(self, connection_id: int, **kwargs) -> CameraConnection:
        """Обновляет связь между камерами"""
        if connection_id <= 0:
            raise ValidationError(f"Invalid connection_id: {connection_id}")

        # Проверяем существование
        existing = self.get_camera_connection(connection_id)
        if not existing:
            raise NotFoundError(f"Camera connection with id {connection_id} not found")

        allowed_fields = {'bidirectional', 'weight', 'metadata'}
        update_fields = []
        values = []

        for field, value in kwargs.items():
            if field not in allowed_fields:
                raise ValidationError(f"Invalid field for update: {field}")

            if field == 'metadata' and value is not None:
                value = json.dumps(value)

            update_fields.append(f"{field} = %s")
            values.append(value)

        if not update_fields:
            return existing

        values.append(connection_id)
        update_query = f"UPDATE camera_connections SET {', '.join(update_fields)} WHERE id = %s RETURNING *"

        with self._get_connection() as conn:
            try:
                with self._transaction(conn):
                    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                        cursor.execute(update_query, values)
                        row = cursor.fetchone()
                        if not row:
                            raise RepositoryError("Failed to update camera connection")

                        logger.info(f"Updated camera connection with id {connection_id}")
                        return CameraConnection.from_db_row(dict(row))

            except Exception as e:
                logger.error(f"Error updating camera connection {connection_id}: {e}", exc_info=True)
                raise RepositoryError(f"Failed to update camera connection: {e}")

    def get_camera_connection(self, connection_id: int) -> Optional[CameraConnection]:
        """Получает связь по ID"""
        if connection_id <= 0:
            raise ValidationError(f"Invalid connection_id: {connection_id}")

        with self._get_connection() as conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("""
                        SELECT id, source_camera_id, source_segment, target_camera_id, target_segment,
                               bidirectional, weight, metadata, created_at
                        FROM camera_connections
                        WHERE id = %s
                    """, (connection_id,))

                    row = cursor.fetchone()
                    if row:
                        return CameraConnection.from_db_row(dict(row))
                    return None

            except Exception as e:
                logger.error(f"Error getting camera connection {connection_id}: {e}", exc_info=True)
                raise RepositoryError(f"Failed to get camera connection: {e}")

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
                raise RepositoryError(f"Failed to remove camera connection: {e}")

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
                raise RepositoryError(f"Failed to remove connections: {e}")

    def _validate_connection_input(self, source_camera_id: int, source_segment: str,
                                    target_camera_id: int, target_segment: str, weight: float):
        """Валидирует входные данные для связи"""
        if source_camera_id <= 0:
            raise ValidationError(f"Invalid source_camera_id: {source_camera_id}")
        if target_camera_id <= 0:
            raise ValidationError(f"Invalid target_camera_id: {target_camera_id}")
        if not source_segment or not target_segment:
            raise ValidationError("Segment names cannot be empty")
        if weight <= 0:
            raise ValidationError(f"Weight must be positive, got {weight}")
        if source_camera_id == target_camera_id:
            raise ValidationError("Source and target cameras must be different")

    # === Вспомогательные методы ===

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

    def get_database_stats(self) -> Dict[str, Any]:
        """Получает статистику по БД"""
        with self._get_connection() as conn:
            try:
                with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                    stats = {}

                    # Количество камер
                    cursor.execute("SELECT COUNT(*) as count FROM cameras")
                    stats['cameras'] = cursor.fetchone()['count']

                    # Количество контейнеров
                    cursor.execute("SELECT COUNT(*) as count FROM parking_containers")
                    stats['containers'] = cursor.fetchone()['count']

                    # Количество активных занятостей
                    cursor.execute("SELECT COUNT(*) as count FROM spot_occupancy WHERE occupied_until IS NULL")
                    stats['occupied_spots'] = cursor.fetchone()['count']

                    # Количество связей между камерами
                    cursor.execute("SELECT COUNT(*) as count FROM camera_connections")
                    stats['camera_connections'] = cursor.fetchone()['count']

                    return stats

            except Exception as e:
                logger.error(f"Error getting database stats: {e}", exc_info=True)
                raise RepositoryError(f"Failed to get database stats: {e}")

