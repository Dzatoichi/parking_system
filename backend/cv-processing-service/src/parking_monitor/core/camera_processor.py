# core/camera_processor.py

import threading
import queue
import time
import cv2
import numpy as np
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from ultralytics import YOLO

from parking_monitor.core.scene3d import Scene3D, CarDetection
from parking_monitor.core.ray_proj_new_seg import DirectionTracker, calculate_enhanced_center


def _allow_trusted_yolo_checkpoint_load() -> None:
    """Allow loading trusted Ultralytics checkpoints under PyTorch 2.6+."""
    try:
        import torch
    except Exception:
        return

    if getattr(torch.load, "_parking_monitor_patched", False):
        return

    original_load = torch.load

    def patched_load(*args, **kwargs):
        kwargs.setdefault("weights_only", False)
        return original_load(*args, **kwargs)

    patched_load._parking_monitor_patched = True
    torch.load = patched_load


@dataclass
class ProcessorMessage:
    """Сообщение от CameraProcessor в ParkingMonitor"""
    camera_id: int
    frame_number: int
    timestamp: float
    cars_3d: List  # список Car3D из Scene3D
    departed: List[tuple]  # [(track_id, segment), ...]
    new_tracks: List[tuple]  # [(track_id, features), ...] для новых автомобилей


class CameraProcessor:
    """
    Обработчик видеопотока одной камеры.
    Запускается в отдельном потоке, общается с ParkingMonitor через очереди.
    """

    def __init__(
            self,
            camera_id: int,
            video_path: str,
            scene_3d: Scene3D,
            model_path: str = "best.pt",
            process_every_n: int = 10,  # обрабатывать каждый 3-й кадр
            outgoing_queue: Optional[queue.Queue] = None,
            frame_callback: Optional[callable] = None  # новый параметр
    ):
        self.camera_id = camera_id
        self.video_path = video_path
        self.scene = scene_3d
        self.outgoing_queue = outgoing_queue
        self.frame_callback = frame_callback

        # Модель YOLO
        model_candidate = Path(model_path)
        if not model_candidate.exists():
            bundled_model = Path(__file__).resolve().parents[1] / model_path
            if bundled_model.exists():
                model_path = str(bundled_model)
        self.model_path = model_path
        tracker_path = Path(__file__).resolve().parents[1] / "vehicle_botsort_conf.yaml"
        self.tracker_config_path = str(tracker_path) if tracker_path.exists() else "vehicle_botsort_conf.yaml"
        _allow_trusted_yolo_checkpoint_load()
        self.model = YOLO(model_path)

        # Трекер направлений
        self.tracker = DirectionTracker()

        # Настройки обработки
        self.process_every_n = process_every_n

        # Для работы с видео
        self.cap = None
        self.fps = 30  # будет определено при открытии
        self.frame_count = 0
        self.processed_count = 0

        # Управление потоком
        self.is_running = False
        self.thread = None
        self.paused = False

        # Очередь входящих заданий (от ParkingMonitor)
        self.incoming_queue = queue.Queue(maxsize=100)

        # Кэш треков для отслеживания исчезновений
        self.active_tracks = {}  # track_id -> последняя позиция, сегмент и т.д.

    def start(self):
        """Запускает поток обработки"""
        if self.thread and self.thread.is_alive():
            return

        self.is_running = True
        self.thread = threading.Thread(target=self._process_loop)
        self.thread.daemon = True
        self.thread.start()
        print(f"CameraProcessor {self.camera_id} started")

    def stop(self):
        """Останавливает поток"""
        self.is_running = False
        if self.thread:
            self.thread.join(timeout=5.0)
        if self.cap and self.cap.isOpened():
            self.cap.release()
        print(f"CameraProcessor {self.camera_id} stopped")

    def pause(self):
        """Приостанавливает обработку"""
        self.paused = True

    def resume(self):
        """Возобновляет обработку"""
        self.paused = False

    def send_command(self, command: Dict[str, Any]):
        """Отправляет команду процессору (из основного потока)"""
        self.incoming_queue.put(command)

    def _process_loop(self):
        """Основной цикл обработки видео"""
        # Открываем видео
        self.cap = cv2.VideoCapture(self.video_path)
        if not self.cap.isOpened():
            print(f"ERROR: Cannot open video {self.video_path}")
            return

        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))

        print(f"Camera {self.camera_id}: FPS={self.fps}, total frames={total_frames}")

        self.frame_count = 0

        while self.is_running:
            # Проверяем команды
            self._process_commands()

            if self.paused:
                time.sleep(0.1)
                continue

            # Читаем кадр
            ret, frame = self.cap.read()
            if not ret:
                # Видео закончилось - можно зациклить или остановить
                print(f"Camera {self.camera_id}: end of video")
                break

            self.frame_count += 1

            # Пропускаем кадры для производительности
            if self.frame_count % self.process_every_n != 0:
                continue

            self.processed_count += 1
            timestamp = self.frame_count / self.fps

            # Обрабатываем кадр
            cars_3d, departed, new_tracks = self._process_frame(frame, timestamp)

            # Отправляем результаты в монитор
            if self.outgoing_queue and (cars_3d or departed or new_tracks):
                msg = ProcessorMessage(
                    camera_id=self.camera_id,
                    frame_number=self.processed_count,
                    timestamp=timestamp,
                    cars_3d=cars_3d,
                    departed=departed,
                    new_tracks=new_tracks
                )
                self.outgoing_queue.put(msg)

        self.cap.release()
        print(f"CameraProcessor {self.camera_id} finished")

    def _process_commands(self):
        """Обрабатывает входящие команды от монитора"""
        try:
            while True:  # обрабатываем все команды в очереди
                cmd = self.incoming_queue.get_nowait()

                # if cmd['type'] == 'SEARCH_VEHICLE':
                #     # Начинаем искать конкретный автомобиль
                #     track_id = cmd['track_id']
                #     features = cmd.get('features')
                #     expected_segment = cmd.get('expected_segment')
                #
                #     print(f"Camera {self.camera_id}: searching for vehicle {track_id}")
                #     # TODO: добавить в список поиска
                #
                # elif cmd['type'] == 'STOP_SEARCH':
                #     track_id = cmd['track_id']
                #     print(f"Camera {self.camera_id}: stop searching for {track_id}")
                #     # TODO: убрать из списка поиска

        except queue.Empty:
            pass

    def _process_frame(self, frame, timestamp):
        """Обрабатывает один кадр"""
        # Детекция YOLO

        results = self.model.track(
            frame,
            conf=0.35,
            iou=0.5,
            tracker=self.tracker_config_path,
            persist=True,
            verbose=False,
        )

        # Извлекаем детекции
        detections = []
        active_tracks = set()
        new_tracks_info = []  # для новых автомобилей

        if (results[0].boxes is not None and
                results[0].boxes.id is not None):

            track_ids = results[0].boxes.id.cpu().numpy().astype(int)
            boxes = results[0].boxes.xyxy.cpu().numpy()

            for i, (box, track_id) in enumerate(zip(boxes, track_ids)):
                # Вычисляем центр по bbox
                center_x = (box[0] + box[2]) / 2
                center_y = (box[1] + box[3]) / 2
                center_2d = np.array([center_x, center_y])

                # Получаем направление (без изменений)
                direction = self.tracker.update(track_id, center_2d)

                # Создаём CarDetection (сегмент больше не нужен)
                detections.append(CarDetection(
                    track_id=int(track_id),
                    center=center_2d,
                    direction=direction
                ))

                # Если трек новый, запоминаем для реидентификации
                # if track_id not in self.active_tracks:
                #     # TODO: извлечь признаки для реидентификации
                #     features = self._extract_features(frame, segment_scaled)
                #     new_tracks_info.append((track_id, features))

                # Обновляем кэш треков
                # self.active_tracks[track_id] = {
                #     'last_position': center_2d,
                #     'last_frame': self.processed_count,
                #     'bbox': boxes[i] if i < len(boxes) else None
                # }

        # Очищаем трекер
        self.tracker.cleanup(active_tracks)

        # Определяем, кто покинул кадр
        # departed = self._find_departed_tracks(active_tracks, frame.shape)

        departed = []

        # Добавляем детекции в 3D сцену
        cars_3d = self.scene.add_detections(
            detections,
            self.processed_count,
            timestamp
        )

        # --- Добавляем визуализацию и callback ---
        if self.frame_callback:
            # Рисуем аннотации YOLO (маски, bbox, треки)
            annotated_frame = results[0].plot()  # BGR numpy array
            # Можно дополнительно нарисовать центры, направления, но это опционально
            self.frame_callback(self.camera_id, annotated_frame, timestamp, self.processed_count)

        return cars_3d, departed, new_tracks_info

    def _process_frame_segmentation(self, frame, timestamp):
        """Обрабатывает один кадр"""
        # Детекция YOLO

        results = self.model.track(
            frame,
            conf=0.35,
            iou=0.5,
            tracker=self.tracker_config_path,
            persist=True,
            verbose=False,
        )

        # Извлекаем детекции
        detections = []
        active_tracks = set()
        new_tracks_info = []  # для новых автомобилей

        if (results[0].masks is not None and
                results[0].boxes is not None and
                results[0].boxes.id is not None):

            track_ids = results[0].boxes.id.cpu().numpy().astype(int)
            segments = results[0].masks.xyn
            boxes = results[0].boxes.xyxy.cpu().numpy()

            for i, (segment, track_id) in enumerate(zip(segments, track_ids)):
                if len(segment) < 3:
                    continue

                active_tracks.add(track_id)

                # Масштабируем сегмент
                segment_scaled = segment.copy()
                segment_scaled[:, 0] = segment[:, 0] * frame.shape[1]
                segment_scaled[:, 1] = segment[:, 1] * frame.shape[0]

                # Вычисляем центр
                center_x, center_y = calculate_enhanced_center(
                    segment_scaled,
                    boxes[i] if i < len(boxes) else None
                )
                center_2d = np.array([center_x, center_y])

                # Получаем направление
                direction = self.tracker.update(track_id, center_2d)

                # Если трек новый, запоминаем для реидентификации
                # if track_id not in self.active_tracks:
                #     # TODO: извлечь признаки для реидентификации
                #     features = self._extract_features(frame, segment_scaled)
                #     new_tracks_info.append((track_id, features))

                # Обновляем кэш треков
                # self.active_tracks[track_id] = {
                #     'last_position': center_2d,
                #     'last_frame': self.processed_count,
                #     'bbox': boxes[i] if i < len(boxes) else None
                # }

                # Создаем детекцию
                detections.append(CarDetection(
                    track_id=int(track_id),
                    center=center_2d,
                    direction=direction
                ))

        # Очищаем трекер
        self.tracker.cleanup(active_tracks)

        # Определяем, кто покинул кадр
        # departed = self._find_departed_tracks(active_tracks, frame.shape)

        departed = []

        # Добавляем детекции в 3D сцену
        cars_3d = self.scene.add_detections(
            detections,
            self.processed_count,
            timestamp
        )

        # --- Добавляем визуализацию и callback ---
        if self.frame_callback:
            # Рисуем аннотации YOLO (маски, bbox, треки)
            annotated_frame = results[0].plot()  # BGR numpy array
            # Можно дополнительно нарисовать центры, направления, но это опционально
            self.frame_callback(self.camera_id, annotated_frame, timestamp, self.processed_count)

        return cars_3d, departed, new_tracks_info

    def _find_departed_tracks(self, active_tracks, frame_shape):
        """Находит треки, которые исчезли, и определяет сегмент выезда"""
        departed = []

        # Какие треки были активны, но сейчас исчезли
        disappeared = set(self.active_tracks.keys()) - active_tracks

        for track_id in disappeared:
            track_info = self.active_tracks.get(track_id)
            if track_info and track_info['last_frame'] == self.processed_count - 1:
                # Исчез на предыдущем кадре - определяем сегмент
                segment = self._determine_exit_segment(
                    track_info['last_position'],
                    track_info.get('bbox'),
                    frame_shape
                )
                departed.append((track_id, segment))

            # Удаляем из кэша
            self.active_tracks.pop(track_id, None)

        return departed

    def _determine_exit_segment(self, last_position, bbox, frame_shape):
        """
        Определяет, через какой сегмент кадра уехал автомобиль.
        Возвращает строку типа "bottom_3", "right_2" и т.д.
        """
        h, w = frame_shape[:2]
        x, y = last_position

        # Получаем конфигурацию сегментов из БД (будет передана)
        # Пока используем заглушку
        h_segments = 8  # горизонтальных сегментов
        v_segments = 5  # вертикальных

        # Определяем, к какой границе ближе
        dist_to_left = x
        dist_to_right = w - x
        dist_to_top = y
        dist_to_bottom = h - y

        min_dist = min(dist_to_left, dist_to_right, dist_to_top, dist_to_bottom)

        if min_dist == dist_to_left:
            # Уехал влево
            seg_num = min(v_segments, int((y / h) * v_segments) + 1)
            return f"left_{seg_num}"
        elif min_dist == dist_to_right:
            # Уехал вправо
            seg_num = min(v_segments, int((y / h) * v_segments) + 1)
            return f"right_{seg_num}"
        elif min_dist == dist_to_top:
            # Уехал вверх
            seg_num = min(h_segments, int((x / w) * h_segments) + 1)
            return f"top_{seg_num}"
        else:
            # Уехал вниз
            seg_num = min(h_segments, int((x / w) * h_segments) + 1)
            return f"bottom_{seg_num}"

    def _extract_features(self, frame, segment):
        """Извлекает признаки автомобиля для реидентификации"""
        # TODO: использовать ReID модель
        # Пока заглушка
        return np.random.rand(512)  # 512-мерный вектор


# Заглушка для обратной совместимости
def process_video(*args, **kwargs):
    print("WARNING: process_video is deprecated, use CameraProcessor")
    return 0
