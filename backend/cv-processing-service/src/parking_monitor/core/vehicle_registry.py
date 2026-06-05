import numpy as np
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple, Any
from enum import Enum
import threading
import time


class VehicleStatus(Enum):
    """Статус автомобиля в системе"""
    ENTERING = "entering"  # Только въехал, ищет место
    MOVING = "moving"  # Движется по парковке
    PARKING = "parking"  # Процесс парковки (маневрирует)
    PARKED = "parked"  # Припаркован
    EXITING = "exiting"  # Выезжает
    LEFT = "left"  # Покинул парковку


@dataclass
class VehiclePosition:
    """Позиция автомобиля в определенный момент времени"""
    camera_id: int
    point_3d: np.ndarray  # (x, y, z) в мировых координатах
    container_id: int = -1  # -1 если не на месте
    timestamp: float = 0.0
    frame: int = 0


@dataclass
class VehicleInfo:
    """Полная информация об автомобиле"""
    # Основные данные
    track_id: int  # глобальный ID в системе
    features: np.ndarray  # вектор признаков для реидентификации
    license_plate: Optional[str] = None  # госномер (если распознан)

    # Временные метки
    first_seen: float = 0.0  # timestamp первого появления
    last_seen: float = 0.0  # timestamp последнего обновления
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None

    # Статус
    status: VehicleStatus = VehicleStatus.ENTERING

    # Текущая позиция
    current_camera: Optional[int] = None
    current_position: Optional[np.ndarray] = None
    current_container: int = -1
    current_direction: Optional[np.ndarray] = None  # вектор направления

    # История перемещений
    positions: List[VehiclePosition] = field(default_factory=list)
    camera_history: List[int] = field(default_factory=list)  # какие камеры видели
    visited_containers: Set[int] = field(default_factory=set)  # на каких местах был

    # Для трекинга
    last_update_frame: int = 0
    confidence: float = 1.0  # уверенность в идентификации

    def add_position(self, camera_id: int, point_3d: np.ndarray,
                     container_id: int, timestamp: float, frame: int):
        """Добавляет позицию в историю"""
        pos = VehiclePosition(
            camera_id=camera_id,
            point_3d=point_3d.copy(),
            container_id=container_id,
            timestamp=timestamp,
            frame=frame
        )
        self.positions.append(pos)

        # Ограничиваем историю (последние 1000 позиций)
        if len(self.positions) > 1000:
            self.positions = self.positions[-1000:]

        # Обновляем текущие данные
        self.current_camera = camera_id
        self.current_position = point_3d.copy()
        self.current_container = container_id
        self.last_seen = timestamp
        self.last_update_frame = frame

        # Добавляем в историю камер, если новая
        if not self.camera_history or self.camera_history[-1] != camera_id:
            self.camera_history.append(camera_id)

        # Добавляем в посещенные контейнеры
        if container_id != -1:
            self.visited_containers.add(container_id)

    def set_direction(self, direction: Optional[np.ndarray]):
        """Устанавливает направление движения"""
        if direction is not None:
            self.current_direction = direction.copy()
        else:
            self.current_direction = None

    def is_parked(self) -> bool:
        """Проверяет, припаркован ли автомобиль"""
        return self.status == VehicleStatus.PARKED

    def get_recent_positions(self, count: int = 10) -> List[VehiclePosition]:
        """Возвращает последние N позиций"""
        return self.positions[-count:]

    def get_path_3d(self) -> np.ndarray:
        """Возвращает массив точек для отрисовки пути"""
        if len(self.positions) < 2:
            return np.array([])
        return np.array([p.point_3d for p in self.positions])


class VehicleRegistry:
    """
    Реестр всех автомобилей на парковке.
    Хранит глобальное состояние и обеспечивает реидентификацию.
    Потокобезопасен (использует блокировки).
    """

    def __init__(self, reid_threshold: float = 0.75, feature_size: int = 512):
        self.lock = threading.RLock()

        # Основное хранилище
        self.vehicles: Dict[int, VehicleInfo] = {}  # track_id -> VehicleInfo
        self.next_track_id: int = 1

        # Индексы для быстрого поиска
        self.active_vehicles: Set[int] = set()  # track_id тех, кто в движении
        self.parked_vehicles: Dict[int, int] = {}  # container_id -> track_id
        self.camera_vehicles: Dict[int, Set[int]] = {}  # camera_id -> set(track_id)

        # Параметры реидентификации
        self.reid_threshold = reid_threshold
        self.feature_size = feature_size

        # Кэш признаков для быстрого сравнения
        self.feature_cache: Dict[int, np.ndarray] = {}  # track_id -> features

        # Статистика
        self.stats = {
            'total_vehicles': 0,
            'currently_parked': 0,
            'currently_moving': 0,
            'reidentified_count': 0,
            'missed_count': 0
        }

    # === Основные операции ===

    def register_new_vehicle(self,
                             track_id: int,  # локальный ID с камеры
                             features: np.ndarray,
                             entry_camera: int,
                             entry_time: float,
                             license_plate: Optional[str] = None) -> int:
        """
        Регистрирует новый автомобиль в системе.
        Возвращает глобальный track_id.
        """
        with self.lock:
            global_id = self.next_track_id
            self.next_track_id += 1

            vehicle = VehicleInfo(
                track_id=global_id,
                features=features.copy(),
                license_plate=license_plate,
                first_seen=entry_time,
                last_seen=entry_time,
                status=VehicleStatus.ENTERING,
                current_camera=entry_camera
            )

            self.vehicles[global_id] = vehicle
            self.active_vehicles.add(global_id)
            self.feature_cache[global_id] = features.copy()

            # Добавляем в индекс по камерам
            if entry_camera not in self.camera_vehicles:
                self.camera_vehicles[entry_camera] = set()
            self.camera_vehicles[entry_camera].add(global_id)

            self.stats['total_vehicles'] += 1
            self.stats['currently_moving'] += 1

            print(f"VehicleRegistry: registered new vehicle {global_id} on camera {entry_camera}")
            return global_id

    def update_vehicle(self, track_id: int, camera_id: int,
                       position: Optional[np.ndarray], container_id: int,
                       timestamp: float, frame: int,
                       direction: Optional[np.ndarray] = None) -> bool:
        with self.lock:
            if track_id not in self.vehicles:
                return False

            vehicle = self.vehicles[track_id]

            # Добавляем позицию только если она не None
            if position is not None:
                pos = VehiclePosition(
                    camera_id=camera_id,
                    point_3d=position.copy(),
                    container_id=container_id,
                    timestamp=timestamp,
                    frame=frame
                )
                vehicle.positions.append(pos)
                if len(vehicle.positions) > 1000:
                    vehicle.positions = vehicle.positions[-1000:]

                vehicle.current_position = position.copy()
                vehicle.current_container = container_id
                vehicle.last_seen = timestamp
                vehicle.last_update_frame = frame

                # История камер
                if not vehicle.camera_history or vehicle.camera_history[-1] != camera_id:
                    vehicle.camera_history.append(camera_id)

                # Посещённые контейнеры
                if container_id != -1:
                    vehicle.visited_containers.add(container_id)

            # Обновляем текущую камеру всегда
            vehicle.current_camera = camera_id

            if direction is not None:
                vehicle.set_direction(direction)

            # Проверяем, не сменился ли статус
            was_parked = (vehicle.status == VehicleStatus.PARKED)
            is_parked_now = (container_id != -1)

            # # Добавляем позицию
            # vehicle.add_position(camera_id, position, container_id, timestamp, frame)

            if direction is not None:
                vehicle.set_direction(direction)

            # Обновляем статус
            if was_parked and not is_parked_now:
                # Только что выехал с места
                vehicle.status = VehicleStatus.MOVING
                self.active_vehicles.add(track_id)
                if vehicle.current_container in self.parked_vehicles:
                    del self.parked_vehicles[vehicle.current_container]
                self.stats['currently_parked'] -= 1
                self.stats['currently_moving'] += 1
                print(f"Vehicle {track_id} left parking spot {vehicle.current_container}")

            elif not was_parked and is_parked_now:
                # Только что припарковался
                vehicle.status = VehicleStatus.PARKING
                # Не меняем parked_vehicles пока, подтвердим после стабилизации

            # Обновляем индекс по камерам
            if camera_id not in self.camera_vehicles:
                self.camera_vehicles[camera_id] = set()
            self.camera_vehicles[camera_id].add(track_id)

            return True

    def confirm_parked(self, track_id: int, container_id: int):
        """
        Подтверждает, что автомобиль действительно припарковался.
        (Вызывается после нескольких кадров стабильности)
        """
        with self.lock:
            if track_id not in self.vehicles:
                return

            vehicle = self.vehicles[track_id]
            old_status = vehicle.status
            vehicle.status = VehicleStatus.PARKED
            vehicle.current_container = container_id

            # Обновляем parked_vehicles
            self.parked_vehicles[container_id] = track_id

            # Убираем из active если был там
            if track_id in self.active_vehicles:
                self.active_vehicles.remove(track_id)

            # Обновляем статистику
            if old_status != VehicleStatus.PARKED:
                self.stats['currently_parked'] += 1
                self.stats['currently_moving'] -= 1
                print(f"Vehicle {track_id} confirmed parked on spot {container_id}")

    def mark_exited(self, track_id: int, exit_time: float, exit_camera: int):
        """
        Отмечает автомобиль как покинувший парковку.
        """
        with self.lock:
            if track_id not in self.vehicles:
                return

            vehicle = self.vehicles[track_id]
            vehicle.status = VehicleStatus.LEFT
            vehicle.exit_time = datetime.fromtimestamp(exit_time)

            # Освобождаем место, если было занято
            if vehicle.current_container != -1:
                if vehicle.current_container in self.parked_vehicles:
                    del self.parked_vehicles[vehicle.current_container]
                self.stats['currently_parked'] -= 1

            # Убираем из активных
            if track_id in self.active_vehicles:
                self.active_vehicles.remove(track_id)
                self.stats['currently_moving'] -= 1

            # Убираем из индексов камер
            for cam_id in list(self.camera_vehicles.keys()):
                if track_id in self.camera_vehicles[cam_id]:
                    self.camera_vehicles[cam_id].remove(track_id)

            print(f"Vehicle {track_id} exited parking from camera {exit_camera}")

    # === Реидентификация ===

    def reidentify(self, features: np.ndarray, camera_id: int) -> Optional[int]:
        """
        Пытается найти соответствие по признакам среди активных автомобилей.
        Возвращает track_id или None.
        """
        with self.lock:
            if len(self.active_vehicles) == 0:
                return None

            best_match = None
            best_score = -1

            # Ищем только среди активных (припаркованные не двигаются)
            for track_id in self.active_vehicles:
                if track_id not in self.feature_cache:
                    continue

                # Косинусное расстояние
                feat1 = self.feature_cache[track_id]
                feat2 = features

                # Нормализуем
                norm1 = np.linalg.norm(feat1)
                norm2 = np.linalg.norm(feat2)

                if norm1 == 0 or norm2 == 0:
                    continue

                score = np.dot(feat1, feat2) / (norm1 * norm2)

                if score > self.reid_threshold and score > best_score:
                    best_score = score
                    best_match = track_id

            if best_match is not None:
                self.stats['reidentified_count'] += 1
                # Обновляем кэш признаков (адаптация)
                alpha = 0.7
                self.feature_cache[best_match] = (
                        alpha * self.feature_cache[best_match] +
                        (1 - alpha) * features
                )
                # Нормализуем
                self.feature_cache[best_match] /= np.linalg.norm(self.feature_cache[best_match])

            return best_match

    def update_features(self, track_id: int, features: np.ndarray):
        """Обновляет признаки автомобиля (адаптация)"""
        with self.lock:
            if track_id in self.feature_cache:
                alpha = 0.9  # медленная адаптация
                self.feature_cache[track_id] = (
                        alpha * self.feature_cache[track_id] +
                        (1 - alpha) * features
                )
                self.feature_cache[track_id] /= np.linalg.norm(self.feature_cache[track_id])

    # === Запросы состояния ===

    def get_vehicle(self, track_id: int) -> Optional[VehicleInfo]:
        """Возвращает информацию об автомобиле"""
        with self.lock:
            return self.vehicles.get(track_id)

    def get_vehicle_at_spot(self, container_id: int) -> Optional[int]:
        """Возвращает track_id автомобиля на указанном месте"""
        with self.lock:
            return self.parked_vehicles.get(container_id)

    def get_vehicles_on_camera(self, camera_id: int) -> List[int]:
        """Возвращает список track_id на указанной камере"""
        with self.lock:
            return list(self.camera_vehicles.get(camera_id, set()))

    def get_active_vehicles(self) -> List[int]:
        """Возвращает все активные (движущиеся) автомобили"""
        with self.lock:
            return list(self.active_vehicles)

    def get_all_vehicles(self) -> Dict[int, VehicleInfo]:
        """Возвращает копию всех автомобилей"""
        with self.lock:
            return self.vehicles.copy()

    def get_parked_count(self) -> int:
        """Количество припаркованных автомобилей"""
        with self.lock:
            return len(self.parked_vehicles)

    def get_moving_count(self) -> int:
        """Количество движущихся автомобилей"""
        with self.lock:
            return len(self.active_vehicles)

    def get_free_spots(self, all_spots: Set[int]) -> Set[int]:
        """Возвращает множество свободных мест"""
        with self.lock:
            occupied = set(self.parked_vehicles.keys())
            return all_spots - occupied

    def cleanup_stale_vehicles(self, max_age_seconds: float = 30.0):
        """
        Очищает "зависшие" автомобили, которые не обновлялись долгое время.
        Вызывать периодически из монитора.
        """
        with self.lock:
            now = time.time()
            to_remove = []

            for track_id in self.active_vehicles:
                vehicle = self.vehicles.get(track_id)
                if vehicle and (now - vehicle.last_seen) > max_age_seconds:
                    to_remove.append(track_id)

            for track_id in to_remove:
                print(f"VehicleRegistry: cleaning stale vehicle {track_id}")
                if track_id in self.active_vehicles:
                    self.active_vehicles.remove(track_id)
                if track_id in self.feature_cache:
                    del self.feature_cache[track_id]
                # Не удаляем полностью, помечаем как потерянный
                if track_id in self.vehicles:
                    self.vehicles[track_id].status = VehicleStatus.LEFT
                    self.stats['missed_count'] += 1

    def get_statistics(self) -> Dict[str, Any]:
        """Возвращает статистику"""
        with self.lock:
            return self.stats.copy()