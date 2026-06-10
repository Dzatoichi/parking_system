"""
3D Scene - получает 2D детекции, проецирует в 3D и определяет занятость.
"""
import threading

import numpy as np
import cv2
from typing import List, Dict, Optional, Tuple, Set
from dataclasses import dataclass

from scipy.optimize import least_squares

from parking_monitor.db.models import ParkingContainer, CameraCalibration


@dataclass
class CarDetection:
    """Минимальные данные об автомобиле на кадре"""
    track_id: int
    center: np.ndarray  # (x, y) - центр автомобиля на изображении
    direction: Optional[np.ndarray] = None  # (dx, dy) - единичный вектор направления


@dataclass
class Car3D:
    """Автомобиль в 3D сцене"""
    track_id: int
    center: np.ndarray  # (3,) в мировых координатах (Y = center_height)
    direction: Optional[np.ndarray] = None  # (3,) единичный вектор направления
    container_id: int = -1  # ID парковочного места или -1
    frame: int = 0
    timestamp: float = 0.0


# @dataclass
# class SceneFrame:
#     """Один кадр анимации"""
#     frame_number: int
#     timestamp: float
#     cars: List[Car3D] = field(default_factory=list)


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

        # # История
        # self.frames: List[SceneFrame] = []
        # self.current_frame_index: int = 0
        self._current_cars: Dict[int, Car3D] = {}
        self._current_occupancy: Dict[int, Set[int]] = {}

        # Отладка
        self.debug_points: List[np.ndarray] = []

        self._lock = threading.RLock()

    # ====== Управление калибровкой ======

    def set_camera_calibration(self, calibration: CameraCalibration):
        """Устанавливает калибровку камеры"""
        self.camera_calibration = calibration
        self._base_homography = calibration.homography
        self._base_R, _ = cv2.Rodrigues(calibration.rvec)
        self._base_R_inv = np.linalg.inv(self._base_R)
        self._base_tvec = calibration.tvec
        self._base_camera_position = -self._base_R_inv @ self._base_tvec.flatten()

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
        upper_points = world_points_ground + [0, height, 0]

        # Создаем контейнер с сохранением размеров
        container = ParkingContainer(
            id=self._get_next_id(),
            camera_id=self.camera_id,
            name=name,
            ground_points=world_points_ground,
            upper_points=upper_points,
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
        """Создаёт дополнительный контейнер с заданными размерами, используя оптимизацию позы."""
        if self.base_container_id is None:
            raise ValueError("Сначала создайте базовый контейнер")
        if self._base_R is None or self._base_tvec is None or self.camera_calibration is None:
            raise ValueError("Базовый контейнер не имеет калиброванных параметров")

        # Оптимизируем позу
        opt_result = self._optimize_container_pose_by_homography(image_points, length, width, self._base_homography)
        if opt_result is None:
            raise RuntimeError("Не удалось найти подходящую позу контейнера – проверьте точки и размеры")

        ground_points, _, _, _ = opt_result
        upper_points = ground_points + [0, height, 0]

        container = ParkingContainer(
            id=self._get_next_id(),
            camera_id=self.camera_id,
            name=name or f"Container{self.next_container_id}",
            ground_points=ground_points,
            upper_points=upper_points,
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
        """Обновляет контейнер: для базового пересоздаёт, для остальных – оптимизирует позу."""
        if container_id not in self.containers:
            return False

        container: ParkingContainer = self.containers[container_id]
        new_len = length if length is not None else container.length
        new_w = width if width is not None else container.width
        new_h = height if height is not None else container.height

        if container_id == self.base_container_id:
            # Пересоздаём базовый контейнер (сохраняем тот же ID)
            old_id = container_id
            old_name = container.name
            del self.containers[old_id]
            new_id = self.create_base_container(image_points, new_len, new_w, new_h, old_name)
            if new_id != old_id:
                cont_new = self.containers.pop(new_id)
                cont_new.id = old_id
                self.containers[old_id] = cont_new
                if self.base_container_id == new_id:
                    self.base_container_id = old_id
        else:
            # Для обычного контейнера – оптимизация позы
            if self._base_homography is None:
                return False
            opt_result = self._optimize_container_pose_by_homography(image_points, new_len, new_w,
                                                                     self._base_homography)
            if opt_result is None:
                return False

            ground_points, _, _, _ = opt_result
            upper_corners = ground_points + [0, new_h, 0]
            container.ground_points = ground_points
            container.upper_points = upper_corners
            container.image_points = image_points
            container.length = new_len
            container.width = new_w
            container.height = new_h

        return True

    def update_container_3D_points(self, container_id: int, ground_points: np.ndarray) -> bool:
        """
        Обновляет ground_points и upper_points существующего контейнера
        """
        if container_id not in self.containers:
            return False
        if ground_points.shape != (4, 3):
            return False

        container_height = self.containers[container_id].height
        upper_points = ground_points + [0, container_height, 0]

        self.containers[container_id].ground_points = ground_points
        self.containers[container_id].upper_points = upper_points

        return True

    # ====== Методы проекции ======

    @staticmethod
    def _project_3D_points_by_camera(world_pts_3d: np.ndarray, K: np.ndarray, R: np.ndarray,
                                     t: np.ndarray) -> np.ndarray:
        """Проецирует 3D точки в 2D по заданной камере."""
        if world_pts_3d.shape[1] != 3:
            world_pts_3d = world_pts_3d.T
        cam_pts = (R @ world_pts_3d.T).T + t.flatten()
        with np.errstate(divide='ignore', invalid='ignore'):
            u = cam_pts[:, 0] / cam_pts[:, 2]
            v = cam_pts[:, 1] / cam_pts[:, 2]
        fx, fy = K[0, 0], K[1, 1]
        cx, cy = K[0, 2], K[1, 2]
        u_pix = fx * u + cx
        v_pix = fy * v + cy
        return np.stack([u_pix, v_pix], axis=1)

    @staticmethod
    def _project_3D_points_by_homography(points_xz: np.ndarray, homography: np.ndarray) -> np.ndarray:
        """
        Проецирует точки с плоскости пола (X, Z) в изображение (u, v) через гомографию.
        """
        if points_xz.ndim == 1:
            points_xz = points_xz.reshape(1, -1)
        N = points_xz.shape[0]
        # Дополняем до однородных координат (X, Z, 1)
        pts_h = np.hstack([points_xz, np.ones((N, 1))])  # (N, 3)
        proj_h = (homography @ pts_h.T).T  # (N, 3)
        # Нормализация
        with np.errstate(divide='ignore', invalid='ignore'):
            u = proj_h[:, 0] / proj_h[:, 2]
            v = proj_h[:, 1] / proj_h[:, 2]
        return np.stack([u, v], axis=1)

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

    # ====== Методы оптимизации позы ======

    def _optimize_container_pose_by_camera(self, image_points: np.ndarray,
                                           length: float, width: float,
                                           R_cam: np.ndarray, t_cam: np.ndarray,
                                           K: np.ndarray) -> Optional[Tuple[np.ndarray, float, float, float]]:
        """
        Для заданных 2D точек углов и размеров (L,W) при фиксированной камере (R,t,K)
        находит позу (x, z, yaw) прямоугольника, минимизирующую ошибку репроекции.
        Возвращает (ground_corners, x, z, yaw) или None.
        """
        # Локальные углы в системе контейнера (без поворота и переноса)
        local_corners = np.array([
            [0, 0, 0],
            [length, 0, 0],
            [length, 0, width],
            [0, 0, width]
        ], dtype=np.float64)

        # Начальное приближение: центр из image_points проецируем на пол через гомографию
        if self._base_homography is not None:
            pt_h = np.array([np.mean(image_points[:, 0]), np.mean(image_points[:, 1]), 1.0])
            H_inv = np.linalg.inv(self._base_homography)
            world_center = H_inv @ pt_h
            world_center /= world_center[2]
            x0, z0 = world_center[0], world_center[1]
        else:
            x0, z0 = 0.0, 0.0

        # Начальный yaw – угол между первой и второй точкой на изображении
        vec = image_points[1] - image_points[0]
        yaw0 = np.arctan2(vec[1], vec[0])

        params0 = np.array([x0, z0, yaw0], dtype=np.float64)

        def residuals(params):
            x, z, yaw = params
            c, s = np.cos(yaw), np.sin(yaw)
            rot = np.array([[c, 0, s],
                            [0, 1, 0],
                            [-s, 0, c]], dtype=np.float64)
            world_corners = (rot @ local_corners.T).T + np.array([x, 0, z])
            proj = self._project_3D_points_by_camera(world_corners, K, R_cam, t_cam)
            return (proj - image_points).ravel()

        result = least_squares(residuals, params0, method='lm', ftol=1e-8, xtol=1e-8)
        if not result.success:
            return None

        x_opt, z_opt, yaw_opt = result.x
        c, s = np.cos(yaw_opt), np.sin(yaw_opt)
        rot_opt = np.array([[c, 0, s],
                            [0, 1, 0],
                            [-s, 0, c]], dtype=np.float64)
        world_corners = (rot_opt @ local_corners.T).T + np.array([x_opt, 0, z_opt])
        return world_corners.astype(np.float32), x_opt, z_opt, yaw_opt

    def _optimize_container_pose_by_homography(self, image_points: np.ndarray,
                                               length: float, width: float,
                                               homography: np.ndarray) -> Optional[
        Tuple[np.ndarray, float, float, float]]:
        """
        Оптимизирует позу (x, z, yaw) прямоугольного контейнера на полу (Y=0)
        по заданным 2D точкам углов, размерам и гомографии пола.
        """
        if homography is None:
            raise ValueError("Гомография не задана")

        # Локальные углы на полу (XZ)
        local_corners_xz = np.array([
            [0, 0],
            [length, 0],
            [length, width],
            [0, width]
        ], dtype=np.float64)

        # Начальное приближение: центр из 2D -> через гомографию на пол
        center_2d = np.mean(image_points, axis=0)
        pt_h = np.array([center_2d[0], center_2d[1], 1.0])
        H_inv = np.linalg.inv(homography)
        world_center = H_inv @ pt_h
        world_center /= world_center[2]
        x0, z0 = world_center[0], world_center[1]

        # Начальный угол – по первой стороне на изображении
        vec = image_points[1] - image_points[0]
        yaw0 = np.arctan2(vec[1], vec[0])

        params0 = np.array([x0, z0, yaw0], dtype=np.float64)

        def residuals(params):
            x, z, yaw = params
            c, s = np.cos(yaw), np.sin(yaw)
            rot = np.array([[c, -s], [s, c]])
            world_corners_xz = (rot @ local_corners_xz.T).T + np.array([x, z])
            proj = self._project_3D_points_by_homography(world_corners_xz, homography)
            return (proj - image_points).ravel()

        result = least_squares(residuals, params0, method='lm', ftol=1e-8, xtol=1e-8)
        if not result.success:
            return None

        x_opt, z_opt, yaw_opt = result.x

        # Строим 3D углы с поворотом вокруг Y
        c, s = np.cos(yaw_opt), np.sin(yaw_opt)
        R_y = np.array([[c, 0, s],
                        [0, 1, 0],
                        [-s, 0, c]], dtype=np.float32)
        local_3d = np.zeros((4, 3), dtype=np.float32)
        local_3d[:, [0, 2]] = local_corners_xz
        world_ground = (R_y @ local_3d.T).T + np.array([x_opt, 0, z_opt])
        return world_ground.astype(np.float32), x_opt, z_opt, yaw_opt

    def homography_global_optimization(self) -> bool:
        """
        Вычисляет гомографию пола (X,Z) -> (u,v) по всем углам всех контейнеров.
        Обновляет self._base_homography.
        """
        world_pts = []  # (X, Z)
        img_pts = []  # (u, v)
        for cont in self.containers.values():
            if cont.ground_points is None or cont.image_points is None:
                continue
            for i in range(4):
                world_pts.append([cont.ground_points[i, 0], cont.ground_points[i, 2]])
                img_pts.append(cont.image_points[i])
        if len(world_pts) < 4:
            print("Недостаточно точек для гомографии")
            return False
        world_pts = np.array(world_pts, dtype=np.float32)
        img_pts = np.array(img_pts, dtype=np.float32)
        homography, status = cv2.findHomography(world_pts, img_pts, cv2.RANSAC, 3.0)
        if homography is None:
            return False

        self.set_camera_calibration(CameraCalibration(
            id=self.camera_calibration.id,
            container_id=self.camera_calibration.container_id,
            camera_matrix=self.camera_calibration.camera_matrix,
            dist_coeffs=self.camera_calibration.dist_coeffs,
            image_shape=self.camera_calibration.image_shape,
            rvec=self.camera_calibration.rvec,
            tvec=self.camera_calibration.tvec,
            homography=homography
        ))

        return True

    def camera_calibration_global_optimization(self) -> bool:
        """
        Глобальная оптимизация камеры (R,t) с использованием всех точек всех контейнеров.
        Начальное приближение – от базового контейнера.
        """
        # Собираем все 3D точки (X,0,Z) и соответствующие 2D точки
        obj_pts = []  # (X, Z)
        img_pts = []  # (u, v)
        for cont in self.containers.values():
            if cont.ground_points is None or cont.image_points is None:
                continue
            for i in range(4):
                obj_pts.append([cont.ground_points[i, 0], cont.ground_points[i, 2]])
                img_pts.append(cont.image_points[i])
        if len(obj_pts) < 4:
            print("Недостаточно точек")
            return False

        obj_pts = np.array(obj_pts, dtype=np.float64)
        img_pts = np.array(img_pts, dtype=np.float64)
        K = self.camera_calibration.camera_matrix.astype(np.float64)

        # --- Начальное приближение ---
        if self._base_R is not None and self._base_tvec is not None:
            rvec_init, _ = cv2.Rodrigues(self._base_R)
            rvec_init = rvec_init.flatten()
            t_init = self._base_tvec.flatten()
        else:
            # Фоллбек: гомография
            H, _ = cv2.findHomography(obj_pts, img_pts, cv2.RANSAC, 3.0)
            if H is None:
                return False
            ret, rots, trans, norms = cv2.decomposeHomographyMat(H, K)
            if not ret:
                return False
            best = np.argmin([abs(n[1] - 1) for n in norms])
            R_init = rots[best]
            t_init = trans[best].flatten()
            rvec_init, _ = cv2.Rodrigues(R_init)
            rvec_init = rvec_init.flatten()

        # Функция потерь: репроекционная ошибка
        def loss(params):
            rvec = params[:3]
            t = params[3:6]
            R, _ = cv2.Rodrigues(rvec)
            # Проецируем все 3D точки (X,0,Z)
            X = obj_pts[:, 0]
            Z = obj_pts[:, 1]
            ones = np.ones_like(X)
            world_3d = np.vstack([X, np.zeros_like(X), Z])  # (3, N)
            cam_pts = R @ world_3d + t.reshape(3, 1)  # (3, N)
            with np.errstate(divide='ignore', invalid='ignore'):
                u = cam_pts[0, :] / cam_pts[2, :]
                v = cam_pts[1, :] / cam_pts[2, :]
            fx, fy = K[0, 0], K[1, 1]
            cx, cy = K[0, 2], K[1, 2]
            u_proj = fx * u + cx
            v_proj = fy * v + cy
            err = np.hstack([u_proj - img_pts[:, 0], v_proj - img_pts[:, 1]])
            return err

        params0 = np.hstack([rvec_init, t_init])
        result = least_squares(loss, params0, method='lm', max_nfev=5000, ftol=1e-12, xtol=1e-12)
        if not result.success:
            print(f"Оптимизация не удалась: {result.message}")
            return False

        opt_rvec = result.x[:3]
        opt_tvec = result.x[3:6]

        self.set_camera_calibration(CameraCalibration(
            id=self.camera_calibration.id,
            container_id=self.camera_calibration.container_id,
            camera_matrix=self.camera_calibration.camera_matrix,
            dist_coeffs=self.camera_calibration.dist_coeffs,
            image_shape=self.camera_calibration.image_shape,
            rvec=opt_rvec,
            tvec=opt_tvec,
            homography=self.camera_calibration.homography
        ))

        final_err = np.sqrt(np.mean(result.fun ** 2))
        print(f"Глобальная оптимизация успешна, средняя ошибка: {final_err:.2f} пикселей")
        return True

    # ====== Добавление кадра ======

    def add_detections(self, detections: List[CarDetection],
                       frame_number: int, timestamp: float):
        with self._lock:
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

    # Новый метод для получения текущих автомобилей
    def get_current_cars(self) -> List[Car3D]:
        with self._lock:
            return list(self._current_cars.values())

    # # ====== История (без изменений) ======
    #
    # def get_frame(self, index: int) -> Optional[SceneFrame]:
    #     if 0 <= index < len(self.frames):
    #         return self.frames[index]
    #     return None
    #
    # def get_current_frame(self) -> Optional[SceneFrame]:
    #     return self.get_frame(self.current_frame_index)
    #
    # def next_frame(self):
    #     if self.current_frame_index < len(self.frames) - 1:
    #         self.current_frame_index += 1
    #         self._current_cars = {car.track_id: car for car in self.frames[self.current_frame_index].cars}
    #         self._update_occupancy()
    #
    # def prev_frame(self):
    #     if self.current_frame_index > 0:
    #         self.current_frame_index -= 1
    #         self._current_cars = {car.track_id: car for car in self.frames[self.current_frame_index].cars}
    #         self._update_occupancy()
    #
    # def clear_history(self):
    #     self.frames.clear()
    #     self.current_frame_index = 0
    #     self._current_cars.clear()
    #     self._current_occupancy.clear()
