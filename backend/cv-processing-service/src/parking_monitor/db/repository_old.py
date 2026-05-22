# db/repository.py

import json
import numpy as np
from typing import List, Optional, Dict, Any, Tuple
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from datetime import datetime

from parking_monitor.db.models import Camera, SegmentsConfig, ParkingContainer, CameraCalibration


class ParkingRepository:
    """
    Репозиторий для работы с базой данных парковки.
    Инкапсулирует все SQL запросы.
    """

    def __init__(self, connection_pool: pool.SimpleConnectionPool):
        self.pool = connection_pool

    # === Камеры ===

    def get_all_cameras(self) -> List[Camera]:
        """Получает все камеры"""
        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT id, video_path, name, location, segments_config_id, created_at
                    FROM cameras
                    ORDER BY id
                """)
                return [Camera.from_db_row(row) for row in cursor.fetchall()]
        finally:
            self.pool.putconn(conn)

    def get_camera(self, camera_id: int) -> Optional[Camera]:
        """Получает камеру по ID"""
        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT id, video_path, name, location, segments_config_id, created_at
                    FROM cameras
                    WHERE id = %s
                """, (camera_id,))
                row = cursor.fetchone()
                return Camera.from_db_row(row) if row else None
        finally:
            self.pool.putconn(conn)

    def add_camera(self, video_path: str, name: str, segments_config_id: int,
                   location: str = "") -> Camera:
        """Добавляет новую камеру"""
        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    INSERT INTO cameras (video_path, name, location, segments_config_id)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id, video_path, name, location, segments_config_id, created_at
                """, (video_path, name, location, segments_config_id))
                row = cursor.fetchone()
                conn.commit()
                return Camera.from_db_row(row)
        finally:
            self.pool.putconn(conn)

    # === Конфигурации сегментов ===

    def get_all_segments_configs(self) -> List[SegmentsConfig]:
        """Получает все конфигурации сегментов"""
        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT id, name, horizontal_segments, vertical_segments, description, created_at
                    FROM segments_configs
                    ORDER BY name
                """)
                return [SegmentsConfig.from_db_row(row) for row in cursor.fetchall()]
        finally:
            self.pool.putconn(conn)

    # === Парковочные контейнеры ===

    def get_camera_containers(self, camera_id: int) -> List[ParkingContainer]:
        """Получает все контейнеры для камеры"""
        conn = self.pool.getconn()
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
                    # Парсим JSON поля
                    row['ground_points'] = json.loads(row['ground_points'])
                    row['upper_points'] = json.loads(row['upper_points'])
                    if row['image_points']:
                        row['image_points'] = json.loads(row['image_points'])
                    containers.append(ParkingContainer.from_db_row(row))

                return containers
        finally:
            self.pool.putconn(conn)

    def get_container(self, container_id: int) -> Optional[ParkingContainer]:
        """Получает контейнер по ID"""
        conn = self.pool.getconn()
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
                    row['ground_points'] = json.loads(row['ground_points'])
                    row['upper_points'] = json.loads(row['upper_points'])
                    if row['image_points']:
                        row['image_points'] = json.loads(row['image_points'])
                    return ParkingContainer.from_db_row(row)
                return None
        finally:
            self.pool.putconn(conn)

    def add_parking_container(self, camera_id: int, name: str,
                              length: float, width: float, height: float,
                              ground_points: List[Tuple[float, float, float]],
                              upper_points: List[Tuple[float, float, float]],
                              image_points: Optional[List[Tuple[float, float]]] = None,
                              is_base: bool = False) -> ParkingContainer:
        """Добавляет новый парковочный контейнер"""
        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
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
                conn.commit()

                row['ground_points'] = json.loads(row['ground_points'])
                row['upper_points'] = json.loads(row['upper_points'])
                if row['image_points']:
                    row['image_points'] = json.loads(row['image_points'])

                return ParkingContainer.from_db_row(row)
        finally:
            self.pool.putconn(conn)

    # === Калибровка камер ===

    def get_camera_data(self, container_id: int) -> Optional[CameraCalibration]:
        """Получает данные калибровки для контейнера (обычно для базового)"""
        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT id, container_id, camera_matrix, rvec, tvec, dist_coeffs, image_shape, created_at
                    FROM camera_calibration
                    WHERE container_id = %s
                """, (container_id,))

                row = cursor.fetchone()
                if row:
                    # Парсим JSON в numpy массивы
                    row['camera_matrix'] = np.array(json.loads(row['camera_matrix']), dtype=np.float32)
                    row['rvec'] = np.array(json.loads(row['rvec']), dtype=np.float32)
                    row['tvec'] = np.array(json.loads(row['tvec']), dtype=np.float32)
                    row['dist_coeffs'] = np.array(json.loads(row['dist_coeffs']), dtype=np.float32)
                    row['image_shape'] = tuple(json.loads(row['image_shape']))
                    return CameraCalibration.from_db_row(row)
                return None
        finally:
            self.pool.putconn(conn)

    def add_camera_calibration(self, container_id: int,
                               camera_matrix: np.ndarray,
                               rvec: np.ndarray,
                               tvec: np.ndarray,
                               dist_coeffs: np.ndarray,
                               image_shape: Tuple[int, int]) -> CameraCalibration:
        """Добавляет данные калибровки"""
        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
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
                conn.commit()

                row['camera_matrix'] = np.array(json.loads(row['camera_matrix']), dtype=np.float32)
                row['rvec'] = np.array(json.loads(row['rvec']), dtype=np.float32)
                row['tvec'] = np.array(json.loads(row['tvec']), dtype=np.float32)
                row['dist_coeffs'] = np.array(json.loads(row['dist_coeffs']), dtype=np.float32)
                row['image_shape'] = tuple(json.loads(row['image_shape']))

                return CameraCalibration.from_db_row(row)
        finally:
            self.pool.putconn(conn)

    # === Занятость мест ===

    def mark_spot_occupied(self, spot_id: int, vehicle_track_id: int):
        """Отмечает место как занятое"""
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cursor:
                # Закрываем предыдущую запись, если есть
                cursor.execute("""
                    UPDATE spot_occupancy 
                    SET occupied_until = NOW()
                    WHERE spot_id = %s AND occupied_until IS NULL
                """, (spot_id,))

                # Создаем новую
                cursor.execute("""
                    INSERT INTO spot_occupancy (spot_id, vehicle_track_id, occupied_since)
                    VALUES (%s, %s, NOW())
                """, (spot_id, vehicle_track_id))

                conn.commit()
        finally:
            self.pool.putconn(conn)

    def mark_spot_free(self, spot_id: int):
        """Отмечает место как свободное"""
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    UPDATE spot_occupancy 
                    SET occupied_until = NOW()
                    WHERE spot_id = %s AND occupied_until IS NULL
                """, (spot_id,))
                conn.commit()
        finally:
            self.pool.putconn(conn)

    def get_current_occupancy(self) -> Dict[int, int]:
        """Возвращает текущую занятость: {spot_id: vehicle_track_id}"""
        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT spot_id, vehicle_track_id
                    FROM spot_occupancy
                    WHERE occupied_until IS NULL
                """)
                return {row['spot_id']: row['vehicle_track_id'] for row in cursor.fetchall()}
        finally:
            self.pool.putconn(conn)

    # db/repository.py (добавить в класс ParkingRepository)

    def get_all_camera_connections(self) -> List[Dict]:
        """
        Получает все связи между камерами.
        """
        conn = self.pool.getconn()
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
                return [dict(row) for row in rows]
        finally:
            self.pool.putconn(conn)

    def get_camera_connections(self, camera_id: int) -> List[Dict]:
        """
        Получает все исходящие связи для конкретной камеры.
        """
        conn = self.pool.getconn()
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
                return [dict(row) for row in rows]
        finally:
            self.pool.putconn(conn)

    def add_camera_connection(self,
                              source_camera_id: int,
                              source_segment: str,
                              target_camera_id: int,
                              target_segment: str,
                              bidirectional: bool = True,
                              weight: float = 1.0,
                              metadata: Optional[Dict] = None) -> Optional[int]:
        """
        Добавляет связь между камерами.
        Возвращает ID созданной связи или None.
        """
        conn = self.pool.getconn()
        try:
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
                conn.commit()
                return result[0] if result else None
        except Exception as e:
            print(f"Error adding camera connection: {e}")
            conn.rollback()
            return None
        finally:
            self.pool.putconn(conn)

    def remove_camera_connection(self, connection_id: int) -> bool:
        """
        Удаляет связь по ID.
        """
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM camera_connections
                    WHERE id = %s
                """, (connection_id,))

                conn.commit()
                return cursor.rowcount > 0
        finally:
            self.pool.putconn(conn)

    def remove_camera_connections_by_camera(self, camera_id: int) -> int:
        """
        Удаляет все связи с участием камеры.
        Возвращает количество удаленных связей.
        """
        conn = self.pool.getconn()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    DELETE FROM camera_connections
                    WHERE source_camera_id = %s OR target_camera_id = %s
                """, (camera_id, camera_id))

                conn.commit()
                return cursor.rowcount
        finally:
            self.pool.putconn(conn)

    def get_segments_config(self, config_id: int) -> Optional[SegmentsConfig]:
        """
        Получает конфигурацию сегментов по ID.
        """
        conn = self.pool.getconn()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("""
                    SELECT id, name, horizontal_segments, vertical_segments, description, created_at
                    FROM segments_configs
                    WHERE id = %s
                """, (config_id,))

                row = cursor.fetchone()
                if row:
                    return SegmentsConfig.from_db_row(row)
                return None
        finally:
            self.pool.putconn(conn)