"""
3D Scene Manager - получает 2D детекции, проецирует в 3D и определяет занятость.
"""

import numpy as np
import cv2
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass, field

from parking_monitor.db.models import ParkingContainer, CameraCalibration


@dataclass
class CarDetection:
    """Минимальные данные об автомобиле на кадре"""
    track_id: int
    center: np.ndarray  # (x, y) - центр автомобиля на изображении
    direction: Optional[np.ndarray] = None  # (dx, dy) - единичный вектор направления


# @dataclass
# class ParkingContainer3D:
#     """Парковочное место в 3D - основные геометрические данные"""
#     id: int
#     name: str
#     ground_corners: np.ndarray  # (4,3) на полу (Y=0)
#     upper_corners: np.ndarray  # (4,3) на высоте
#     image_points: np.ndarray  # (4,2) на изображении (опционально, для отладки)
#     length: float  # Длина контейнера (по X)
#     width: float  # Ширина контейнера (по Z)
#     height: float  # Высота контейнера
#
#     @property
#     def polygon_xz(self) -> np.ndarray:
#         """Многоугольник на плоскости XZ для проверки принадлежности"""
#         return self.ground_corners[:, [0, 2]]
#
#     @property
#     def center(self) -> np.ndarray:
#         """Центр контейнера"""
#         return np.mean(self.ground_corners, axis=0)
#
#     def contains_point(self, point_xz: np.ndarray) -> bool:
#         """Проверяет, лежит ли точка (X, Z) внутри контейнера"""
#         x, z = point_xz
#         inside = False
#         n = len(self.polygon_xz)
#         for i in range(n):
#             x1, z1 = self.polygon_xz[i]
#             x2, z2 = self.polygon_xz[(i + 1) % n]
#             if ((z1 > z) != (z2 > z)) and (x < (x2 - x1) * (z - z1) / (z2 - z1) + x1):
#                 inside = not inside
#         return inside


# @dataclass
# class CameraCalibration:
#     """Калибровка камеры для проекций"""
#     camera_matrix: np.ndarray  # (3,3) матрица камеры
#     dist_coeffs: np.ndarray  # коэффициенты дисторсии
#     image_shape: Tuple[int, int]  # (height, width)
#
#     # Вычисляемые свойства
#     @property
#     def fx(self) -> float:
#         return self.camera_matrix[0, 0]
#
#     @property
#     def fy(self) -> float:
#         return self.camera_matrix[1, 1]
#
#     @property
#     def cx(self) -> float:
#         return self.camera_matrix[0, 2]
#
#     @property
#     def cy(self) -> float:
#         return self.camera_matrix[1, 2]
#
#     @classmethod
#     def create_default(cls, image_shape: Tuple[int, int], focal_scale: float = 1.0):
#         """Создает калибровку по умолчанию на основе размера изображения"""
#         h, w = image_shape[:2]
#         focal = max(w, h) * focal_scale
#         camera_matrix = np.array([
#             [focal, 0, w // 2],
#             [0, focal, h // 2],
#             [0, 0, 1]
#         ], dtype=np.float32)
#         dist_coeffs = np.zeros((4, 1))
#         return cls(camera_matrix=camera_matrix, dist_coeffs=dist_coeffs, image_shape=image_shape)

@dataclass
class Car3D:
    """Автомобиль в 3D сцене"""
    track_id: int
    center: np.ndarray  # (3,) в мировых координатах (Y = center_height)
    direction: Optional[np.ndarray] = None  # (3,) единичный вектор направления
    container_id: int = -1  # ID парковочного места или -1
    frame: int = 0
    timestamp: float = 0.0


@dataclass
class SceneFrame:
    """Один кадр анимации"""
    frame_number: int
    timestamp: float
    cars: List[Car3D] = field(default_factory=list)


class Scene3D:
    """
    3D сцена с методами проекции и управления контейнерами
    """

    def __init__(self, camera_id: int):
        # Контейнеры
        self.containers: Dict[int, ParkingContainer] = {}
        self.next_container_id: int = 0

        self.camera_id = camera_id

        # Калибровка камеры
        self.camera_calibration: Optional[CameraCalibration] = None

        # Параметры проекции для базового контейнера
        self.base_container_id: Optional[int] = None
        self._base_homography: Optional[np.ndarray] = None
        self._base_R: Optional[np.ndarray] = None  # матрица поворота
        self._base_R_inv: Optional[np.ndarray] = None  # обратная матрица поворота
        self._base_tvec: Optional[np.ndarray] = None  # вектор трансляции
        self._base_camera_position: Optional[np.ndarray] = None

        # Высота центра автомобиля
        self.center_height: float = 0.5

        # История
        self.frames: List[SceneFrame] = []
        self.current_frame_index: int = 0
        self._current_cars: Dict[int, Car3D] = {}
        self._current_occupancy: Dict[int, Set[int]] = {}

        # Отладка
        self.debug_points: List[np.ndarray] = []

    # ====== Управление калибровкой ======

    def set_camera_calibration(self, calibration: CameraCalibration):
        """Устанавливает калибровку камеры"""
        self.camera_calibration = calibration
        if calibration.homography is not None:
            self._base_homography = calibration.homography
        else:
            self._base_homography = None

    def set_camera_from_image(self, image_shape: Tuple[int, int], focal_scale: float = 1.0):
        """Создает калибровку по умолчанию из размера изображения"""
        self.camera_calibration = CameraCalibration.create_default(image_shape, focal_scale)

    # ====== Создание контейнеров ======

    def create_base_container(self, image_points: np.ndarray,
                              length: float, width: float, height: float,
                              name: str = "BaseContainer") -> int:
        """
        Создаёт базовый контейнер и вычисляет все параметры проекции
        Принимает размеры из GUI
        """
        if self.camera_calibration is None:
            raise ValueError("Сначала установите калибровку камеры")

        # Мировые координаты для базового контейнера
        world_points_ground = np.array([
            [0, 0, 0],
            [length, 0, 0],
            [length, 0, width],
            [0, 0, width]
        ], dtype=np.float32)

        # Вычисляем гомографию
        H, _ = cv2.findHomography(world_points_ground[:, [0, 2]],
                                  image_points.astype(np.float32))
        if H is None:
            raise ValueError("Не удалось вычислить гомографию")
        self._base_homography = H
        if self.camera_calibration is not None:
            self.camera_calibration.homography = self._base_homography

        # Вычисляем PnP
        success, rvec, tvec = cv2.solvePnP(
            world_points_ground,
            image_points.astype(np.float32),
            self.camera_calibration.camera_matrix,
            self.camera_calibration.dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE
        )

        if success:
            self._base_R, _ = cv2.Rodrigues(rvec)
            self._base_R_inv = np.linalg.inv(self._base_R)
            self._base_tvec = tvec
            self._base_camera_position = -self._base_R_inv @ tvec.flatten()

        # Верхние углы
        upper_corners = world_points_ground + [0, height, 0]

        # Создаем контейнер с сохранением размеров
        container = ParkingContainer(
            id=self._get_next_id(),
            camera_id=self.camera_id,
            name=name,
            ground_points=world_points_ground,
            upper_points=upper_corners,
            image_points=image_points,
            length=length,
            width=width,
            height=height
        )

        self.containers[container.id] = container
        self.base_container_id = container.id
        return container.id

    def create_container(self, image_points: np.ndarray,
                         length: float, width: float, height: float,
                         name: Optional[str] = None) -> int:
        """
        Создаёт дополнительный контейнер с заданными размерами
        Использует параметры проекции из базового контейнера
        """
        if self.base_container_id is None:
            raise ValueError("Сначала создайте базовый контейнер")

        # Проецируем 2D углы в 3D через базовый контейнер
        world_points = []
        for pt in image_points:
            world_pt = self._project_image_to_ground(pt)
            world_points.append(world_pt)
        world_points = np.array(world_points)

        # Верхние углы
        upper_corners = world_points + [0, height, 0]

        # Имя по умолчанию
        if name is None:
            name = f"Container{self.next_container_id}"

        # Создаем контейнер с переданными размерами
        container = ParkingContainer(
            id=self._get_next_id(),
            camera_id=self.camera_id,
            name=name,
            ground_points=world_points,
            upper_points=upper_corners,
            image_points=image_points,
            length=length,
            width=width,
            height=height
        )

        self.containers[container.id] = container
        return container.id

    def update_container(self, container_id: int, image_points: np.ndarray,
                         length: Optional[float] = None,
                         width: Optional[float] = None,
                         height: Optional[float] = None) -> bool:
        """
        Обновляет существующий контейнер новыми точками и/или размерами
        """
        if container_id not in self.containers:
            return False

        container = self.containers[container_id]

        # Обновляем размеры, если переданы новые
        if length is not None:
            container.length = length
        if width is not None:
            container.width = width
        if height is not None:
            container.height = height

        if container_id == self.base_container_id:
            # Для базового контейнера пересоздаем с новыми размерами
            self.create_base_container(
                image_points=image_points,
                length=container.length,
                width=container.width,
                height=container.height,
                name=container.name
            )
            # Удаляем старый контейнер (create_base_container создаст новый с тем же ID)
            # TODO: аккуратно обработать обновление базового контейнера
        else:
            # Для обычного контейнера пересчитываем мировые координаты
            world_points = []
            for pt in image_points:
                world_pt = self._project_image_to_ground(pt)
                world_points.append(world_pt)
            world_points = np.array(world_points)

            # Верхние углы
            upper_corners = world_points + [0, container.height, 0]

            # Обновляем контейнер
            container.ground_corners = world_points
            container.upper_corners = upper_corners
            container.image_points = image_points

        return True

    # ====== Методы проекции ======

    def _project_image_to_ground(self, point_2d: np.ndarray) -> np.ndarray:
        """Проецирует 2D точку на пол (Y=0) через гомографию"""
        if self._base_homography is None:
            raise ValueError("Нет базовой гомографии")

        pt_h = np.array([point_2d[0], point_2d[1], 1.0])
        H_inv = np.linalg.inv(self._base_homography)
        world_h = H_inv @ pt_h
        world_h /= world_h[2]
        return np.array([world_h[0], 0.0, world_h[1]])

    def project_to_height(self, point_2d: np.ndarray, height: float) -> Optional[np.ndarray]:
        """Лучевая проекция 2D точки на заданную высоту"""
        if (self.camera_calibration is None or
                self._base_R_inv is None or
                self._base_camera_position is None):
            # Fallback на гомографию
            ground = self._project_image_to_ground(point_2d)
            return np.array([ground[0], height, ground[2]])

        # Коррекция дисторсии
        pt = point_2d.reshape(-1, 1, 2).astype(np.float32)
        undist = cv2.undistortPoints(
            pt,
            self.camera_calibration.camera_matrix,
            self.camera_calibration.dist_coeffs,
            P=self.camera_calibration.camera_matrix
        )[0][0]

        # Нормализованные координаты
        x_norm = (undist[0] - self.camera_calibration.cx) / self.camera_calibration.fx
        y_norm = (undist[1] - self.camera_calibration.cy) / self.camera_calibration.fy

        # Луч в мировых координатах
        ray_cam = np.array([x_norm, y_norm, 1.0])
        ray_world = self._base_R_inv @ ray_cam

        if abs(ray_world[1]) < 1e-6:
            return None

        t = (height - self._base_camera_position[1]) / ray_world[1]
        return self._base_camera_position + t * ray_world

    # ====== Добавление кадра ======

    def add_detections(self, detections: List[CarDetection],
                       frame_number: int, timestamp: float):
        """Добавляет кадр с детекциями"""
        if self.base_container_id is None:
            raise ValueError("Нет базового контейнера для проекции")

        cars_3d = []
        current_tracks = set()

        for detection in detections:
            track_id = detection.track_id
            center_2d = detection.center
            dir_2d = detection.direction

            # Проецируем центр в 3D
            center_3d = self.project_to_height(center_2d, self.center_height)
            if center_3d is None:
                continue

            # Проецируем направление
            direction_3d = None
            if dir_2d is not None:
                dir_point_2d = center_2d + dir_2d * 20
                dir_point_3d = self.project_to_height(dir_point_2d, self.center_height)
                if dir_point_3d is not None:
                    direction_3d = dir_point_3d - center_3d
                    norm = np.linalg.norm(direction_3d)
                    if norm > 0.1:
                        direction_3d = direction_3d / norm

            # Определяем контейнер
            container_id = self._find_container(center_3d[[0, 2]])

            car = Car3D(
                track_id=track_id,
                center=center_3d,
                direction=direction_3d,
                container_id=container_id,
                frame=frame_number,
                timestamp=timestamp
            )
            cars_3d.append(car)
            current_tracks.add(track_id)
            self._current_cars[track_id] = car

        # Очистка исчезнувших машин
        for tid in list(self._current_cars.keys()):
            if tid not in current_tracks:
                del self._current_cars[tid]

        # Обновляем occupancy
        self._update_occupancy()

        # Сохраняем кадр
        frame = SceneFrame(frame_number=frame_number, timestamp=timestamp, cars=cars_3d)
        self.frames.append(frame)

        return cars_3d

    def _find_container(self, point_xz: np.ndarray) -> int:
        """Находит ID контейнера, содержащего точку"""
        for cid, container in self.containers.items():
            if container.contains_point(point_xz):
                return cid
        return -1

    def _update_occupancy(self):
        """Обновляет словарь занятости"""
        occ = {}
        for car in self._current_cars.values():
            if car.container_id != -1:
                occ.setdefault(car.container_id, set()).add(car.track_id)
        self._current_occupancy = occ

    # ====== Вспомогательные методы ======

    def _get_next_id(self) -> int:
        cid = self.next_container_id
        self.next_container_id += 1
        return cid

    def add_debug_point(self, point_3d: np.ndarray):
        self.debug_points.append(point_3d)

    def clear_debug_points(self):
        self.debug_points.clear()

    # ====== Запросы состояния (без изменений) ======

    def get_current_occupancy(self) -> Dict[int, Set[int]]:
        return self._current_occupancy.copy()

    def is_spot_occupied(self, spot_id: int) -> bool:
        return spot_id in self._current_occupancy

    def get_cars_in_spot(self, spot_id: int) -> Set[int]:
        return self._current_occupancy.get(spot_id, set())

    def get_free_spots(self) -> List[int]:
        all_spots = set(self.containers.keys())
        occupied = set(self._current_occupancy.keys())
        return list(all_spots - occupied)

    # ====== История (без изменений) ======

    def get_frame(self, index: int) -> Optional[SceneFrame]:
        if 0 <= index < len(self.frames):
            return self.frames[index]
        return None

    def get_current_frame(self) -> Optional[SceneFrame]:
        return self.get_frame(self.current_frame_index)

    def next_frame(self):
        if self.current_frame_index < len(self.frames) - 1:
            self.current_frame_index += 1
            self._current_cars = {car.track_id: car for car in self.frames[self.current_frame_index].cars}
            self._update_occupancy()

    def prev_frame(self):
        if self.current_frame_index > 0:
            self.current_frame_index -= 1
            self._current_cars = {car.track_id: car for car in self.frames[self.current_frame_index].cars}
            self._update_occupancy()

    def clear_history(self):
        self.frames.clear()
        self.current_frame_index = 0
        self._current_cars.clear()
        self._current_occupancy.clear()
