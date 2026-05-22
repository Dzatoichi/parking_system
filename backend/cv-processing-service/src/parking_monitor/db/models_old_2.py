# db/models.py

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Tuple, Any, Union
import numpy as np
import logging

logger = logging.getLogger(__name__)


@dataclass
class Camera:
    """Модель камеры из БД"""
    id: int
    video_path: str
    name: str
    location: str
    segments_config_id: int
    created_at: datetime

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
            created_at=row['created_at']
        )

    def to_dict(self) -> dict:
        """Конвертирует объект в словарь"""
        return {
            'id': self.id,
            'video_path': self.video_path,
            'name': self.name,
            'location': self.location,
            'segments_config_id': self.segments_config_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
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

        # Валидация
        if row['horizontal_segments'] <= 0 or row['vertical_segments'] <= 0:
            raise ValueError("Horizontal and vertical segments must be positive")

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
    """Парковочный контейнер из БД"""
    id: int
    camera_id: int
    name: str
    length: float
    width: float
    height: float
    ground_points: List[Tuple[float, float, float]]  # 4 точки (x,y,z) на полу
    upper_points: List[Tuple[float, float, float]]  # 4 точки на высоте
    image_points: Optional[List[Tuple[float, float]]]  # 4 точки на изображении (для отладки)
    is_base: bool
    created_at: datetime
    updated_at: datetime

    def __post_init__(self):
        """Валидация после инициализации"""
        self._validate_points()
        self._validate_dimensions()

    def _validate_points(self):
        """Проверяет корректность точек"""
        if len(self.ground_points) != 4:
            raise ValueError(f"Expected 4 ground points, got {len(self.ground_points)}")

        if len(self.upper_points) != 4:
            raise ValueError(f"Expected 4 upper points, got {len(self.upper_points)}")

        if self.image_points and len(self.image_points) != 4:
            raise ValueError(f"Expected 4 image points, got {len(self.image_points)}")

        # Проверка размерности точек
        for points, name in [(self.ground_points, 'ground'), (self.upper_points, 'upper')]:
            for i, point in enumerate(points):
                if len(point) != 3:
                    raise ValueError(f"{name} point {i} must have 3 coordinates, got {len(point)}")

        if self.image_points:
            for i, point in enumerate(self.image_points):
                if len(point) != 2:
                    raise ValueError(f"image point {i} must have 2 coordinates, got {len(point)}")

    def _validate_dimensions(self):
        """Проверяет корректность размеров"""
        if self.length <= 0:
            raise ValueError(f"Length must be positive, got {self.length}")
        if self.width <= 0:
            raise ValueError(f"Width must be positive, got {self.width}")
        if self.height <= 0:
            raise ValueError(f"Height must be positive, got {self.height}")

    @classmethod
    def from_db_row(cls, row: dict) -> 'ParkingContainer':
        """Создает объект ParkingContainer из строки БД"""
        if not row:
            raise ValueError("Row cannot be empty")

        required_fields = ['id', 'camera_id', 'name', 'length', 'width', 'height',
                           'ground_points', 'upper_points', 'created_at', 'updated_at']
        for field in required_fields:
            if field not in row:
                raise ValueError(f"Missing required field: {field}")

        # Парсинг точек с проверкой
        ground_points = cls._parse_points(row['ground_points'], expected_dim=3)
        upper_points = cls._parse_points(row['upper_points'], expected_dim=3)
        image_points = cls._parse_points(row.get('image_points'), expected_dim=2) if row.get('image_points') else None

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
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

    @staticmethod
    def _parse_points(data: Any, expected_dim: int) -> List[Tuple]:
        """Парсит точки из JSON данных"""
        if data is None:
            return []

        if isinstance(data, str):
            import json
            data = json.loads(data)

        if not isinstance(data, (list, tuple)):
            raise ValueError(f"Expected list or tuple, got {type(data)}")

        points = []
        for i, item in enumerate(data):
            if not isinstance(item, (list, tuple)):
                raise ValueError(f"Point {i} must be list or tuple, got {type(item)}")

            if len(item) != expected_dim:
                raise ValueError(f"Point {i} must have {expected_dim} coordinates, got {len(item)}")

            # Конвертируем все значения в float
            point = tuple(float(x) for x in item)
            points.append(point)

        return points

    def to_dict(self) -> dict:
        """Конвертирует объект в словарь для JSON"""
        import json

        def convert_points(points):
            return [list(p) for p in points]

        return {
            'id': self.id,
            'camera_id': self.camera_id,
            'name': self.name,
            'length': self.length,
            'width': self.width,
            'height': self.height,
            'ground_points': convert_points(self.ground_points),
            'upper_points': convert_points(self.upper_points),
            'image_points': convert_points(self.image_points) if self.image_points else None,
            'is_base': self.is_base,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


@dataclass
class CameraCalibration:
    """Калибровка камеры для проекции"""
    id: int
    container_id: int  # ссылка на базовый контейнер
    camera_matrix: np.ndarray  # 3x3
    rvec: np.ndarray  # вектор поворота
    tvec: np.ndarray  # вектор трансляции
    dist_coeffs: np.ndarray  # коэффициенты дисторсии
    image_shape: Tuple[int, int]  # (height, width)
    created_at: datetime

    def __post_init__(self):
        """Валидация после инициализации"""
        self._validate_arrays()

    def _validate_arrays(self):
        """Проверяет корректность массивов"""
        if self.camera_matrix.shape != (3, 3):
            raise ValueError(f"Camera matrix must be 3x3, got {self.camera_matrix.shape}")

        if self.rvec.shape not in [(3, 1), (3,)]:
            raise ValueError(f"rvec must be 3x1 or 3, got {self.rvec.shape}")

        if self.tvec.shape not in [(3, 1), (3,)]:
            raise ValueError(f"tvec must be 3x1 or 3, got {self.tvec.shape}")

        if len(self.image_shape) != 2:
            raise ValueError(f"image_shape must be (height, width), got {self.image_shape}")

    @classmethod
    def from_db_row(cls, row: dict) -> 'CameraCalibration':
        """Создает объект CameraCalibration из строки БД"""
        if not row:
            raise ValueError("Row cannot be empty")

        required_fields = ['id', 'container_id', 'camera_matrix', 'rvec',
                           'tvec', 'dist_coeffs', 'image_shape', 'created_at']
        for field in required_fields:
            if field not in row:
                raise ValueError(f"Missing required field: {field}")

        # Парсим JSON в numpy массивы
        camera_matrix = cls._parse_numpy_array(row['camera_matrix'], shape=(3, 3))
        rvec = cls._parse_numpy_array(row['rvec'], expected_shape=(3,))
        tvec = cls._parse_numpy_array(row['tvec'], expected_shape=(3,))
        dist_coeffs = cls._parse_numpy_array(row['dist_coeffs'])
        image_shape = cls._parse_tuple(row['image_shape'], expected_length=2)

        return cls(
            id=int(row['id']),
            container_id=int(row['container_id']),
            camera_matrix=camera_matrix,
            rvec=rvec,
            tvec=tvec,
            dist_coeffs=dist_coeffs,
            image_shape=image_shape,
            created_at=row['created_at']
        )

    @staticmethod
    def _parse_numpy_array(data: Any, shape: Optional[tuple] = None,
                           expected_shape: Optional[tuple] = None) -> np.ndarray:
        """Парсит JSON в numpy массив"""
        import json

        if isinstance(data, str):
            data = json.loads(data)

        if not isinstance(data, (list, tuple)):
            raise ValueError(f"Expected list or tuple, got {type(data)}")

        arr = np.array(data, dtype=np.float32)

        if shape and arr.shape != shape:
            raise ValueError(f"Expected shape {shape}, got {arr.shape}")

        if expected_shape:
            if len(arr.shape) != len(expected_shape):
                raise ValueError(f"Expected {len(expected_shape)} dimensions, got {len(arr.shape)}")

            for i, (actual, expected) in enumerate(zip(arr.shape, expected_shape)):
                if actual != expected and expected != -1:
                    raise ValueError(f"Dimension {i}: expected {expected}, got {actual}")

        return arr

    @staticmethod
    def _parse_tuple(data: Any, expected_length: int) -> tuple:
        """Парсит JSON в tuple"""
        import json

        if isinstance(data, str):
            data = json.loads(data)

        if not isinstance(data, (list, tuple)):
            raise ValueError(f"Expected list or tuple, got {type(data)}")

        if len(data) != expected_length:
            raise ValueError(f"Expected {expected_length} elements, got {len(data)}")

        return tuple(int(x) if isinstance(x, (int, float)) else x for x in data)

    def to_dict(self) -> dict:
        """Конвертирует объект в словарь для JSON"""
        import json

        return {
            'id': self.id,
            'container_id': self.container_id,
            'camera_matrix': self.camera_matrix.tolist(),
            'rvec': self.rvec.tolist(),
            'tvec': self.tvec.tolist(),
            'dist_coeffs': self.dist_coeffs.tolist(),
            'image_shape': list(self.image_shape),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }