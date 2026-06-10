# db/models.py

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Tuple, Dict, Any
import json
import logging

import numpy as np

logger = logging.getLogger(__name__)


class SpotStatus(Enum):
    FREE = "free"
    PARKING_PENDING = "parking_pending"   # замечен автомобиль, но ещё не подтверждён
    PARKING_CONFIRMED = "parking_confirmed"

@dataclass
class ParkingSpotState:
    spot_id: int
    status: SpotStatus = SpotStatus.FREE
    vehicle_track_id: Optional[int] = None
    first_seen_time: Optional[float] = None   # timestamp первого появления на этом месте
    last_seen_time: Optional[float] = None
    confirmed_time: Optional[datetime] = None  # когда подтвердили парковку
    consecutive_frames: int = 0               # сколько кадров подряд стоит на месте

@dataclass
class Camera:
    """Модель камеры из БД"""
    id: int
    video_path: str
    name: str
    location: str
    segments_config_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None  # Добавляем поле updated_at
    is_active: bool = True  # Добавляем поле с значением по умолчанию

    @classmethod
    def from_db_row(cls, row: dict) -> 'Camera':
        """Создает объект Camera из строки БД"""
        if not row:
            raise ValueError("Row cannot be empty")

        required_fields = ['id', 'video_path', 'name', 'segments_config_id', 'created_at']
        for field in required_fields:
            if field not in row:
                raise ValueError(f"Missing required field: {field}")

        return cls(
            id=int(row['id']),
            video_path=str(row['video_path']),
            name=str(row['name']),
            location=str(row.get('location', '')),
            segments_config_id=int(row['segments_config_id']),
            is_active=bool(row.get('is_active', True)),
            created_at=row['created_at'],
            updated_at=row.get('updated_at')
        )

    def to_dict(self) -> dict:
        """Конвертирует объект в словарь"""
        return {
            'id': self.id,
            'video_path': self.video_path,
            'name': self.name,
            'location': self.location,
            'segments_config_id': self.segments_config_id,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


@dataclass
class SegmentsConfig:
    """Конфигурация сегментов кадра"""
    id: int
    name: str
    horizontal_segments: int
    vertical_segments: int
    description: Optional[str]
    created_at: datetime

    @classmethod
    def from_db_row(cls, row: dict) -> 'SegmentsConfig':
        """Создает объект SegmentsConfig из строки БД"""
        if not row:
            raise ValueError("Row cannot be empty")

        return cls(
            id=int(row['id']),
            name=str(row['name']),
            horizontal_segments=int(row['horizontal_segments']),
            vertical_segments=int(row['vertical_segments']),
            description=str(row['description']) if row.get('description') else None,
            created_at=row['created_at']
        )

    def to_dict(self) -> dict:
        """Конвертирует объект в словарь"""
        return {
            'id': self.id,
            'name': self.name,
            'horizontal_segments': self.horizontal_segments,
            'vertical_segments': self.vertical_segments,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


@dataclass
class ParkingContainer:
    """Парковочный контейнер из БД - используем numpy для точек"""
    id: int
    camera_id: int
    name: str
    length: float
    width: float
    height: float
    ground_points: np.ndarray  # (4,3) numpy array
    upper_points: np.ndarray  # (4,3) numpy array
    image_points: Optional[np.ndarray] = None  # (4,2) numpy array или None
    is_base: bool = False
    spot_id: Optional[int] = None

    @property
    def polygon_xz(self) -> np.ndarray:
        """Многоугольник на плоскости XZ для проверки принадлежности"""
        return self.ground_points[:, [0, 2]]

    @property
    def center(self) -> np.ndarray:
        """Центр контейнера"""
        return np.mean(self.ground_points, axis=0)

    def contains_point(self, point_xz: np.ndarray) -> bool:
        """Проверяет, лежит ли точка (X, Z) внутри контейнера"""
        x, z = point_xz
        inside = False
        n = len(self.polygon_xz)
        for i in range(n):
            x1, z1 = self.polygon_xz[i]
            x2, z2 = self.polygon_xz[(i + 1) % n]
            if ((z1 > z) != (z2 > z)) and (x < (x2 - x1) * (z - z1) / (z2 - z1) + x1):
                inside = not inside
        return inside

    def __post_init__(self):
        """Валидация после инициализации"""
        # Конвертируем списки в numpy если нужно
        if isinstance(self.ground_points, list):
            self.ground_points = np.array(self.ground_points, dtype=np.float32)
        if isinstance(self.upper_points, list):
            self.upper_points = np.array(self.upper_points, dtype=np.float32)
        if self.image_points is not None and isinstance(self.image_points, list):
            self.image_points = np.array(self.image_points, dtype=np.float32)

        # Валидация формы
        if self.ground_points.shape != (4, 3):
            raise ValueError(f"ground_points must be (4,3), got {self.ground_points.shape}")
        if self.upper_points.shape != (4, 3):
            raise ValueError(f"upper_points must be (4,3), got {self.upper_points.shape}")
        if self.image_points is not None and self.image_points.shape != (4, 2):
            raise ValueError(f"image_points must be (4,2), got {self.image_points.shape}")

        # Валидация размеров
        if self.length <= 0 or self.width <= 0 or self.height <= 0:
            raise ValueError(f"Dimensions must be positive: {self.length}x{self.width}x{self.height}")

    @classmethod
    def from_db_row(cls, row: dict) -> 'ParkingContainer':
        """Создает объект ParkingContainer из строки БД"""
        if not row:
            raise ValueError("Row cannot be empty")

        required_fields = ['id', 'camera_id', 'name', 'length', 'width', 'height',
                           'ground_points', 'upper_points']
        for field in required_fields:
            if field not in row:
                raise ValueError(f"Missing required field: {field}")

        # Парсинг JSONB в numpy массивы
        ground_points = cls._parse_jsonb_to_numpy(row['ground_points'], expected_shape=(4, 3))
        upper_points = cls._parse_jsonb_to_numpy(row['upper_points'], expected_shape=(4, 3))
        image_points = None
        if row.get('image_points'):
            image_points = cls._parse_jsonb_to_numpy(row['image_points'], expected_shape=(4, 2))

        return cls(
            id=int(row['id']),
            camera_id=int(row['camera_id']),
            name=str(row['name']),
            length=float(row['length']),
            width=float(row['width']),
            height=float(row['height']),
            ground_points=ground_points,
            upper_points=upper_points,
            image_points=image_points,
            is_base=bool(row.get('is_base', False)),
            spot_id=int(row['spot_id']) if row.get('spot_id') is not None else None
        )

    @staticmethod
    def _parse_jsonb_to_numpy(data: Any, expected_shape: Tuple[int, int]) -> np.ndarray:
        """Парсит JSONB в numpy массив"""
        if isinstance(data, str):
            data = json.loads(data)

        if not isinstance(data, (list, tuple)):
            raise ValueError(f"Expected list or tuple, got {type(data)}")

        arr = np.array(data, dtype=np.float32)
        if arr.shape != expected_shape:
            raise ValueError(f"Expected shape {expected_shape}, got {arr.shape}")

        return arr

    def to_db_dict(self) -> dict:
        """Конвертирует объект в словарь для сохранения в БД"""
        return {
            'id': self.id,
            'camera_id': self.camera_id,
            'name': self.name,
            'length': self.length,
            'width': self.width,
            'height': self.height,
            'ground_points': self.ground_points.tolist(),
            'upper_points': self.upper_points.tolist(),
            'image_points': self.image_points.tolist() if self.image_points is not None else None,
            'is_base': self.is_base,
            'spot_id': self.spot_id
        }

    def to_dict(self) -> dict:
        """Конвертирует объект в словарь для JSON (API)"""
        return {
            'id': self.id,
            'camera_id': self.camera_id,
            'name': self.name,
            'length': self.length,
            'width': self.width,
            'height': self.height,
            'ground_points': self.ground_points.tolist(),
            'upper_points': self.upper_points.tolist(),
            'image_points': self.image_points.tolist() if self.image_points is not None else None,
            'is_base': self.is_base,
            'spot_id': self.spot_id
        }


@dataclass
class CameraCalibration:
    """Калибровка камеры для проекции"""
    id: int
    container_id: int
    camera_matrix: np.ndarray  # (3,3)
    dist_coeffs: np.ndarray    # (4,) или (5,)
    image_shape: Tuple[int, int]
    rvec: np.ndarray           # (3,)
    tvec: np.ndarray           # (3,)
    homography: Optional[np.ndarray] = None  # (3,3) матрица гомографии

    # Вычисляемые свойства
    @property
    def fx(self):
        return self.camera_matrix[0, 0]

    @property
    def fy(self):
        return self.camera_matrix[1, 1]

    @property
    def cx(self):
        return self.camera_matrix[0, 2]

    @property
    def cy(self):
        return self.camera_matrix[1, 2]

    @classmethod
    def create_default(cls, image_shape: Tuple[int, int], focal_scale: float = 1.0):
        """Создает калибровку по умолчанию на основе размера изображения"""
        h, w = image_shape[:2]
        focal = max(w, h) * focal_scale
        camera_matrix = np.array([
            [focal, 0, w // 2],
            [0, focal, h // 2],
            [0, 0, 1]
        ], dtype=np.float32)
        dist_coeffs = np.zeros((4, 1))
        return cls(id=-1,
                   container_id=-1,
                   camera_matrix=camera_matrix,
                   dist_coeffs=dist_coeffs,
                   image_shape=image_shape,
                   rvec=np.zeros(3, dtype=np.float32),
                   tvec=np.zeros(3, dtype=np.float32))

    def __post_init__(self):
        """Конвертируем списки в numpy если нужно"""
        if isinstance(self.camera_matrix, list):
            self.camera_matrix = np.array(self.camera_matrix, dtype=np.float32)
        if isinstance(self.rvec, list):
            self.rvec = np.array(self.rvec, dtype=np.float32)
        if isinstance(self.tvec, list):
            self.tvec = np.array(self.tvec, dtype=np.float32)
        if isinstance(self.dist_coeffs, list):
            self.dist_coeffs = np.array(self.dist_coeffs, dtype=np.float32)
        if isinstance(self.homography, list):
            self.homography = np.array(self.homography, dtype=np.float32)

        # Валидация
        if self.camera_matrix.shape != (3, 3):
            raise ValueError(f"camera_matrix must be (3,3), got {self.camera_matrix.shape}")
        if self.rvec.shape != (3,):
            raise ValueError(f"rvec must be (3,), got {self.rvec.shape}")
        if self.tvec.shape != (3,):
            raise ValueError(f"tvec must be (3,), got {self.tvec.shape}")
        if self.homography is not None and self.homography.shape != (3, 3):
            raise ValueError(f"homography must be (3,3), got {self.homography.shape}")

    @classmethod
    def from_db_row(cls, row: dict) -> 'CameraCalibration':
        """Создает объект CameraCalibration из строки БД"""
        if not row:
            raise ValueError("Row cannot be empty")

        required_fields = ['id', 'container_id', 'camera_matrix', 'rvec',
                           'tvec', 'dist_coeffs', 'image_shape']
        for field in required_fields:
            if field not in row:
                raise ValueError(f"Missing required field: {field}")

        # Парсинг JSONB в numpy
        camera_matrix = cls._parse_jsonb_to_numpy(row['camera_matrix'], expected_shape=(3, 3))
        rvec = cls._parse_jsonb_to_numpy(row['rvec'], expected_shape=(3,))
        tvec = cls._parse_jsonb_to_numpy(row['tvec'], expected_shape=(3,))
        dist_coeffs = cls._parse_jsonb_to_numpy(row['dist_coeffs'])
        image_shape = cls._parse_tuple(row['image_shape'], expected_length=2)
        homography = None
        if row.get('homography'):
            homography = cls._parse_jsonb_to_numpy(row['homography'], expected_shape=(3, 3))

        return cls(
            id=int(row['id']),
            container_id=int(row['container_id']),
            camera_matrix=camera_matrix,
            rvec=rvec,
            tvec=tvec,
            dist_coeffs=dist_coeffs,
            image_shape=image_shape,
            homography=homography
        )

    @staticmethod
    def _parse_jsonb_to_numpy(data: Any, expected_shape: Optional[Tuple[int, ...]] = None) -> np.ndarray:
        """Парсит JSONB в numpy массив"""
        if isinstance(data, str):
            data = json.loads(data)

        if not isinstance(data, (list, tuple)):
            raise ValueError(f"Expected list or tuple, got {type(data)}")

        arr = np.array(data, dtype=np.float32)
        if expected_shape and arr.shape != expected_shape:
            raise ValueError(f"Expected shape {expected_shape}, got {arr.shape}")

        return arr

    @staticmethod
    def _parse_tuple(data: Any, expected_length: int) -> tuple:
        """Парсит JSONB в tuple"""
        if isinstance(data, str):
            data = json.loads(data)

        if not isinstance(data, (list, tuple)):
            raise ValueError(f"Expected list or tuple, got {type(data)}")

        if len(data) != expected_length:
            raise ValueError(f"Expected {expected_length} elements, got {len(data)}")

        return tuple(data)

    def to_db_dict(self) -> dict:
        """Конвертирует объект в словарь для сохранения в БД"""
        result = {
            'id': self.id,
            'container_id': self.container_id,
            'camera_matrix': self.camera_matrix.tolist(),
            'rvec': self.rvec.tolist(),
            'tvec': self.tvec.tolist(),
            'dist_coeffs': self.dist_coeffs.tolist(),
            'image_shape': list(self.image_shape)
        }

        if self.homography is not None:
            result['homography'] = self.homography.tolist()
        return result

    def to_dict(self) -> dict:
        """Конвертирует объект в словарь для JSON (API)"""
        result = {
            'id': self.id,
            'container_id': self.container_id,
            'camera_matrix': self.camera_matrix.tolist(),
            'rvec': self.rvec.tolist(),
            'tvec': self.tvec.tolist(),
            'dist_coeffs': self.dist_coeffs.tolist(),
            'image_shape': list(self.image_shape)
        }

        if self.homography is not None:
            result['homography'] = self.homography.tolist()
        return result


@dataclass
class CameraConnection:
    """Связь между камерами"""
    id: int
    source_camera_id: int
    source_segment: str
    target_camera_id: int
    target_segment: str
    bidirectional: bool
    weight: float
    metadata: Optional[Dict[str, Any]]
    created_at: datetime

    @classmethod
    def from_db_row(cls, row: dict) -> 'CameraConnection':
        """Создает объект CameraConnection из строки БД"""
        if not row:
            raise ValueError("Row cannot be empty")

        metadata = row.get('metadata')
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        return cls(
            id=int(row['id']),
            source_camera_id=int(row['source_camera_id']),
            source_segment=str(row['source_segment']),
            target_camera_id=int(row['target_camera_id']),
            target_segment=str(row['target_segment']),
            bidirectional=bool(row.get('bidirectional', True)),
            weight=float(row.get('weight', 1.0)),
            metadata=metadata,
            created_at=row['created_at']
        )

    def to_dict(self) -> dict:
        """Конвертирует объект в словарь"""
        return {
            'id': self.id,
            'source_camera_id': self.source_camera_id,
            'source_segment': self.source_segment,
            'target_camera_id': self.target_camera_id,
            'target_segment': self.target_segment,
            'bidirectional': self.bidirectional,
            'weight': self.weight,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


@dataclass
class OccupancyRecord:
    """Запись о занятости места"""
    spot_id: int
    vehicle_track_id: int
    occupied_since: datetime
    occupied_until: Optional[datetime] = None

    @classmethod
    def from_db_row(cls, row: dict) -> 'OccupancyRecord':
        """Создает объект OccupancyRecord из строки БД"""
        if not row:
            raise ValueError("Row cannot be empty")

        return cls(
            spot_id=int(row['spot_id']),
            vehicle_track_id=int(row['vehicle_track_id']),
            occupied_since=row['occupied_since'],
            occupied_until=row.get('occupied_until')
        )
