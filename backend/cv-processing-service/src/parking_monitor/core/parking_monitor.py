# core/parking_monitor.py

import threading
import queue
import time
from typing import Dict, Any

import numpy as np

from parking_monitor.db.repository import ParkingRepository
from parking_monitor.db.models import ParkingContainer, ParkingSpotState, SpotStatus

from parking_monitor.core.camera_processor import CameraProcessor, ProcessorMessage
from parking_monitor.core.parking_manager import ParkingSpotManager
from parking_monitor.core.scene3d import Scene3D
from parking_monitor.core.vehicle_registry import VehicleRegistry


class ParkingMonitor:
    """
    Главный оркестратор системы мониторинга парковки.
    Управляет всеми камерами, глобальным состоянием и коммуникацией.
    """

    def __init__(self, db_repo: ParkingRepository):
        self.db = db_repo
        self.spot_manager = None
        self.initialization_mode = True
        self.init_end_time = None

        # Компоненты
        self.vehicle_registry = VehicleRegistry()
        # self.camera_network = CameraNetwork()

        # Данные о камерах
        self.cameras = {}  # camera_id -> camera_info из БД
        self.processors = {}  # camera_id -> CameraProcessor
        self.scenes = {}  # camera_id -> Scene3D
        self.camera_configs = {}  # camera_id -> segments_config

        # Очереди для коммуникации
        self.incoming_queue = queue.Queue(maxsize=1000)  # от процессоров к монитору
        self.processor_queues = {}  # camera_id -> queue (для команд)

        # Поток обработки сообщений
        self.is_running = False
        self.message_thread = None

        # Статистика
        self.stats = {
            'total_frames_processed': 0,
            'total_cars_detected': 0,
            'active_vehicles': 0,
            'parked_vehicles': 0
        }

        self.frame_queues = {}

    def _push_frame(self, camera_id: int, frame: np.ndarray, timestamp: float, frame_num: int):
        """Callback для передачи кадра из процессора в очередь"""
        q = self.frame_queues.get(camera_id)
        if q is not None:
            # Не блокируем, если очередь переполнена – просто пропускаем старые кадры
            try:
                q.put_nowait((frame, timestamp, frame_num))
            except queue.Full:
                pass

    def initialize_from_db(self):
        """
        Загружает все данные из БД и создает процессоры для камер.
        """
        print("Initializing ParkingMonitor from database...")

        # 1. Загружаем конфигурации сегментов
        configs = self.db.get_all_segments_configs()
        for config in configs:
            print(f"  Loaded segments config: {config.name} ({config.horizontal_segments}x{config.vertical_segments})")

        # 2. Загружаем камеры
        db_cameras = self.db.get_all_cameras()
        print(f"  Found {len(db_cameras)} cameras")

        # 3. Загружаем сеть камер (связи)
        # self.camera_network.load_from_db(self.db)

        self.spot_manager = ParkingSpotManager(self.db, confirmation_seconds=1.0, fps_estimate=10)


        # 4. Для каждой камеры создаем Scene3D из сохраненных контейнеров

        for db_camera in db_cameras:
            print(f"  Initializing camera {db_camera.id}: {db_camera.name}")

            if not db_camera.is_active:
                print(f"  Camera {db_camera.id}: {db_camera.name} is inactive, skipping")
                continue

            # Создаем сцену
            scene = Scene3D(db_camera.id)

            # Загружаем контейнеры для этой камеры
            containers = self.db.get_camera_containers(db_camera.id)
            print(f"    Found {len(containers)} parking containers")

            # Сначала восстановим калибровку из базового контейнера
            base_container = next((c for c in containers if c.is_base), None)
            if base_container:
                camera_data = self.db.get_camera_calibration(base_container.id)
                if camera_data:
                    scene.set_camera_calibration(camera_data)
                    print(f"    Restored camera calibration from base container {base_container.id}")

            # Добавляем все контейнеры в сцену
            for container in containers:
                scene.containers[container.id] = ParkingContainer(
                    id=container.id,
                    camera_id=db_camera.id,
                    name=container.name,
                    ground_points=container.ground_points,
                    upper_points=container.upper_points,
                    image_points=container.image_points,
                    length=container.length,
                    width=container.width,
                    height=container.height
                )

                # Если это базовый контейнер, отмечаем
                if container.is_base:
                    scene.base_container_id = container.id

                if container.id not in self.spot_manager.spots:
                    self.spot_manager.spots[container.id] = ParkingSpotState(spot_id=container.id,
                                                                             status=SpotStatus.FREE)

            self.db.initialize_all_spots()

            # Сохраняем сцену
            self.scenes[db_camera.id] = scene

            # Создаем очередь для команд этому процессору
            self.processor_queues[db_camera.id] = queue.Queue()

            self.frame_queues[db_camera.id] = queue.Queue(maxsize=10)

            # Создаем процессор (но пока не запускаем)
            processor = CameraProcessor(
                camera_id=db_camera.id,
                video_path=db_camera.video_path,
                scene_3d=scene,
                outgoing_queue=self.incoming_queue,
                frame_callback=self._push_frame
            )

            self.processors[db_camera.id] = processor
            self.cameras[db_camera.id] = db_camera


        print("Initialization complete")

    def start(self):
        """Запускает монитор и все процессоры"""
        self.initialization_mode = True
        self.init_end_time = time.time() + 3.0  # 30 секунд

        if self.is_running:
            return

        self.is_running = True

        # Запускаем поток обработки сообщений
        self.message_thread = threading.Thread(target=self._message_loop)
        self.message_thread.daemon = True
        self.message_thread.start()

        # Запускаем все процессоры
        for camera_id, processor in self.processors.items():
            processor.start()

        print("ParkingMonitor started")

    def stop(self):
        """Останавливает монитор и все процессоры"""
        self.is_running = False

        # Останавливаем процессоры
        for processor in self.processors.values():
            processor.stop()

        # Ждем завершения потока сообщений
        if self.message_thread:
            self.message_thread.join(timeout=5.0)

        print("ParkingMonitor stopped")

    def _message_loop(self):
        """Основной цикл обработки сообщений от процессоров"""
        print("Message loop started")

        while self.is_running:
            try:
                # Получаем сообщение с таймаутом
                msg = self.incoming_queue.get(timeout=0.5)
                self._handle_message(msg)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Error in message loop: {e}")
                # traceback.print_exc()

    # def _handle_message(self, msg: ProcessorMessage):
    #     """
    #     Обрабатывает сообщение от CameraProcessor.
    #     """
    #     # Обновляем статистику
    #     self.stats['total_frames_processed'] += 1
    #     self.stats['total_cars_detected'] += len(msg.cars_3d)

    #     # 1. Обновляем реестр автомобилей
    #     for car in msg.cars_3d:
    #         self.vehicle_registry.update_vehicle(
    #             track_id=car.track_id,
    #             camera_id=msg.camera_id,
    #             position=car.center,
    #             container_id=car.container_id,
    #             direction=car.direction,
    #             timestamp=msg.timestamp,
    #             frame=msg.frame_number
    #         )

    #         # Обновляем состояние места
    #         if car.container_id != -1:
    #             self.spot_manager.update_from_detection(
    #                 car.container_id, car.track_id, msg.timestamp
    #             )
    #         self._update_absent_spots(set(car.container_id for car in msg.cars_3d), msg.timestamp)

    #         # Если инициализационный режим и время вышло – завершить инициализацию
    #         if self.initialization_mode and time.time() > self.init_end_time:
    #             self._finalize_initialization()

        # 2. Обрабатываем новые треки (нужна реидентификация)
        # for track_id, features in msg.new_tracks:
        #     self._handle_new_track(track_id, features, msg.camera_id, msg.timestamp, msg.frame_number)

        # 3. Обрабатываем уехавшие автомобили
        # for track_id, segment in msg.departed:
        #     self._handle_vehicle_departed(track_id, msg.camera_id, segment, msg.timestamp)

        # Обновляем статистику для отладки
        # self.stats['active_vehicles'] = len(self.vehicle_registry.active_vehicles)
        # self.stats['parked_vehicles'] = len(self.vehicle_registry.parked_vehicles)

    def _handle_message(self, msg: ProcessorMessage):
        """
        Обрабатывает сообщение от CameraProcessor.
        """
        # Обновляем статистику
        self.stats["total_frames_processed"] += 1
        self.stats["total_cars_detected"] += len(msg.cars_3d)

        occupied_spots = {
            car.container_id
            for car in msg.cars_3d
            if car.container_id != -1
        }

        for car in msg.cars_3d:
            self.vehicle_registry.update_vehicle(
                track_id=car.track_id,
                camera_id=msg.camera_id,
                position=car.center,
                container_id=car.container_id,
                direction=car.direction,
                timestamp=msg.timestamp,
                frame=msg.frame_number,
            )

            if car.container_id != -1:
                self.spot_manager.update_from_detection(
                    spot_id=car.container_id,
                    track_id=car.track_id,
                    timestamp=msg.timestamp,
                )

        # Вызывается один раз на кадр и только для мест данной камеры
        self._update_absent_spots(
            camera_id=msg.camera_id,
            occupied_set=occupied_spots,
            timestamp=msg.timestamp,
        )

        # Проверка должна выполняться даже при отсутствии автомобилей
        if self.initialization_mode and time.time() > self.init_end_time:
            self._finalize_initialization()

        self.stats["active_vehicles"] = len(
            self.vehicle_registry.active_vehicles
        )
        self.stats["parked_vehicles"] = len(
            self.vehicle_registry.parked_vehicles
        )

    def _finalize_initialization(self):
        """Финализирует инициализацию: подтверждает/освобождает места согласно накопленным данным"""
        self.initialization_mode = False
        # Для каждого места, которое было занято по БД, но не набрало порог – освободить
        for spot_id, state in self.spot_manager.spots.items():
            if state.status == SpotStatus.PARKING_PENDING:
                # Не набрал достаточно кадров – освобождаем в БД и сбрасываем
                if state.vehicle_track_id is not None:
                    self.db.mark_spot_free(spot_id)
                state.status = SpotStatus.FREE
                state.vehicle_track_id = None
            elif state.status == SpotStatus.PARKING_CONFIRMED:
                # Уже подтверждён – ничего не делаем (уже записано в БД)
                pass
        print("Initialization completed, parking spots verified")

    def _update_absent_spots(
        self,
        camera_id: int,
        occupied_set: set[int],
        timestamp: float,
    ):
        """Обновляет отсутствие только для мест указанной камеры."""

        scene = self.scenes.get(camera_id)
        if scene is None:
            return

        camera_spot_ids = set(scene.containers.keys())

        with self.spot_manager.lock:
            for spot_id in camera_spot_ids:
                state = self.spot_manager.spots.get(spot_id)

                if state is None:
                    continue

                if spot_id not in occupied_set and state.status != SpotStatus.FREE:
                    self.spot_manager.update_from_absence(
                        spot_id=spot_id,
                        timestamp=timestamp,
                    )

    # def _handle_new_track(self, track_id, features, camera_id, timestamp, frame):
    #     """
    #     Появился новый трек - пытаемся реидентифицировать или регистрируем новый.
    #     """
    #     # Пытаемся найти соответствие среди известных автомобилей
    #     matched_id = self.vehicle_registry.reidentify(features, camera_id)
    #
    #     if matched_id:
    #         # Нашли соответствие - обновляем
    #         print(f"Reidentified vehicle {matched_id} on camera {camera_id}")
    #         self.vehicle_registry.update_vehicle(
    #             track_id=matched_id,
    #             camera_id=camera_id,
    #             position=None,  # позиция будет в следующем сообщении
    #             container_id=-1,
    #             timestamp=timestamp,
    #             frame=frame
    #         )
    #         # TODO: отправить подтверждение в процессор
    #     else:
    #         # Новый автомобиль - регистрируем
    #         new_id = self.vehicle_registry.register_new_vehicle(
    #             track_id=track_id,
    #             features=features,
    #             entry_camera=camera_id,
    #             entry_time=timestamp
    #         )
    #         print(f"New vehicle registered: {new_id} on camera {camera_id}")
    #
    # def _handle_vehicle_departed(self, track_id, source_camera_id, segment, timestamp):
    #     """
    #     Автомобиль покинул камеру - отправляем задание на следующую.
    #     """
    #     vehicle = self.vehicle_registry.get_vehicle(track_id)
    #     if not vehicle:
    #         print(f"WARNING: Departed vehicle {track_id} not in registry")
    #         return
    #
    #     # Находим следующую камеру через сеть
    #     next_cameras = self.camera_network.get_next_cameras(source_camera_id, segment)
    #
    #     if not next_cameras:
    #         print(f"Vehicle {track_id} left camera {source_camera_id} via {segment} but no next camera defined")
    #         # Возможно, автомобиль покинул парковку
    #         self._handle_vehicle_exited(track_id, source_camera_id, timestamp)
    #         return
    #
    #     print(f"Vehicle {track_id} left camera {source_camera_id} via {segment} -> next: {next_cameras}")
    #
    #     # Для каждой возможной следующей камеры отправляем задание
    #     for target_camera_id, target_segment in next_cameras:
    #         if target_camera_id in self.processor_queues:
    #             self.processor_queues[target_camera_id].put({
    #                 'type': 'SEARCH_VEHICLE',
    #                 'track_id': track_id,
    #                 'features': vehicle.features,
    #                 'expected_segment': target_segment
    #             })

    def _handle_vehicle_parked(self, track_id, container_id):
        """
        Автомобиль припарковался - обновляем статус места в БД.
        """
        vehicle = self.vehicle_registry.get_vehicle(track_id)
        if not vehicle:
            return

        # Если уже был припаркован на другом месте, освобождаем то
        # if vehicle.status == 'PARKED' and vehicle.last_container != container_id:
        #     self.db.mark_spot_free(vehicle.last_container)

        # Отмечаем новое место как занятое
        self.db.mark_spot_occupied(container_id, track_id)

        # Обновляем статус в реестре (уже должно быть сделано в update_vehicle)

    # def _handle_vehicle_exited(self, track_id, last_camera_id, timestamp):
    #     """
    #     Автомобиль покинул парковку.
    #     """
    #     vehicle = self.vehicle_registry.get_vehicle(track_id)
    #     if not vehicle:
    #         return
    #
    #     print(f"Vehicle {track_id} exited parking from camera {last_camera_id}")
    #
    #     # Если был припаркован, освобождаем место
    #     if vehicle.status == 'PARKED' and vehicle.last_container:
    #         self.db.mark_spot_free(vehicle.last_container)
    #
    #     # Отмечаем время выезда
    #     self.vehicle_registry.mark_exited(track_id, timestamp, last_camera_id)
    #
    #     # TODO: записать в историю БД

    def get_status(self) -> Dict[str, Any]:
        """Возвращает текущий статус системы"""
        return {
            'cameras': len(self.processors),
            'active_processors': sum(1 for p in self.processors.values() if p.is_running),
            'stats': self.stats,
            'active_vehicles': len(self.vehicle_registry.active_vehicles),
            'parked_vehicles': len(self.vehicle_registry.parked_vehicles),
            'total_vehicles': len(self.vehicle_registry.vehicles)
        }

    def get_camera_status(self, camera_id: int) -> Dict[str, Any]:
        """Возвращает статус конкретной камеры"""
        processor = self.processors.get(camera_id)
        if not processor:
            return {'error': 'Camera not found'}

        return {
            'camera_id': camera_id,
            'running': processor.is_running,
            'paused': processor.paused,
            'processed_frames': processor.processed_count,
            'active_tracks': len(processor.active_tracks)
        }