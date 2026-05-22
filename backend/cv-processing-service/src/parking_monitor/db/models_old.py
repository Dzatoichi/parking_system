# db/models.py

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Tuple, Any
import numpy as np


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
    def from_db_row(cls, row: dict):
        return cls(
            id=row['id'],
            video_path=row['video_path'],
            name=row['name'],
            location=row.get('location', ''),
            segments_config_id=row['segments_config_id'],
            created_at=row['created_at']
        )


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
    def from_db_row(cls, row: dict):
        return cls(
            id=row['id'],
            name=row['name'],
            horizontal_segments=row['horizontal_segments'],
            vertical_segments=row['vertical_segments'],
            description=row.get('description'),
            created_at=row['created_at']
        )


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

    @classmethod
    def from_db_row(cls, row: dict):
        return cls(
            id=row['id'],
            camera_id=row['camera_id'],
            name=row['name'],
            length=float(row['length']),
            width=float(row['width']),
            height=float(row['height']),
            ground_points=[tuple(p) for p in row['ground_points']],
            upper_points=[tuple(p) for p in row['upper_points']],
            image_points=[tuple(p) for p in row['image_points']] if row.get('image_points') else None,
            is_base=row.get('is_base', False),
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )


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

    @classmethod
    def from_db_row(cls, row: dict):
        return cls(
            id=row['id'],
            container_id=row['container_id'],
            camera_matrix=row['camera_matrix'],
            rvec=row['rvec'],
            tvec=row['tvec'],
            dist_coeffs=row['dist_coeffs'],
            image_shape=row['image_shape'],
            created_at=row['created_at']
        )