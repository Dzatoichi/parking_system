import cv2
import numpy as np
from ultralytics import YOLO
from collections import deque
from typing import List, Optional

from parking_monitor.core.scene3d import CarDetection


class DirectionTracker:
    """Отслеживает направление движения автомобилей по их ID в 2D"""

    def __init__(self, history_size=15, smoothing_factor=0.3, min_history=5):
        self.positions = {}  # {track_id: deque(center_points)}
        self.smooth_directions = {}  # {track_id: (dx, dy)}
        self.history_size = history_size
        self.smoothing_factor = smoothing_factor
        self.min_history = min_history

    def update(self, track_id: int, center_2d: np.ndarray) -> Optional[np.ndarray]:
        """Обновляет позицию и возвращает сглаженный вектор направления в 2D"""
        if track_id not in self.positions:
            self.positions[track_id] = deque(maxlen=self.history_size)
            self.positions[track_id].append(center_2d)
            return None

        self.positions[track_id].append(center_2d)

        if len(self.positions[track_id]) < self.min_history:
            return None

        history = list(self.positions[track_id])
        half_len = len(history) // 3
        if half_len < 1:
            start_points = [history[0]]
            end_points = [history[-1]]
        else:
            start_points = history[:half_len]
            end_points = history[-half_len:]

        start_center = np.mean(start_points, axis=0)
        end_center = np.mean(end_points, axis=0)

        direction = end_center - start_center
        magnitude = np.linalg.norm(direction)
        if magnitude < 1.0:  # минимум 1 пиксель движения
            return None

        direction_normalized = direction / magnitude

        if track_id in self.smooth_directions:
            prev = self.smooth_directions[track_id]
            smooth = self.smoothing_factor * direction_normalized + (1 - self.smoothing_factor) * prev
            smooth = smooth / np.linalg.norm(smooth)
            self.smooth_directions[track_id] = smooth
        else:
            self.smooth_directions[track_id] = direction_normalized

        return self.smooth_directions[track_id]

    def cleanup(self, active_ids: set):
        disappeared = set(self.positions.keys()) - active_ids
        for tid in disappeared:
            self.positions.pop(tid, None)
            self.smooth_directions.pop(tid, None)


def calculate_enhanced_center(segment, bbox=None):
    """
    Вычисляет улучшенный центр автомобиля.

    Args:
        segment: массив точек контура (N, 2) в пикселях
        bbox: bounding box [x1, y1, x2, y2] (опционально)

    Returns:
        center_x, center_y: координаты центра
    """
    # Центр контура (среднее арифметическое всех точек)
    contour_center_x = np.mean(segment[:, 0])
    contour_center_y = np.mean(segment[:, 1])

    if bbox is not None:
        # Центр bounding box
        bbox_center_x = (bbox[0] + bbox[2]) / 2
        bbox_center_y = (bbox[1] + bbox[3]) / 2

        # Усредняем центр контура и центр bounding box
        center_x = (contour_center_x + bbox_center_x) / 2
        center_y = (contour_center_y + bbox_center_y) / 2
    else:
        # Если bbox недоступен, используем только центр контура
        center_x = contour_center_x
        center_y = contour_center_y

    return center_x, center_y


def process_video(video_path, scene, model_path="yolo11n-seg.pt",
                  max_frames=None, callback=None) -> int:
    """
    Обрабатывает видео и добавляет детекции в сцену.
    """
    model = YOLO(model_path)
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Не удалось открыть видео: {video_path}")

    # # Устанавливаем калибровку камеры из первого кадра
    # ret, first_frame = cap.read()
    # if ret:
    #     scene.set_camera_from_image(first_frame.shape)
    #     cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Возвращаемся в начало

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if max_frames:
        total_frames = min(total_frames, max_frames)

    fps = cap.get(cv2.CAP_PROP_FPS)
    process_every_n = max(1, int(fps // 10))

    frame_count = 0
    processed_count = 0
    tracker = DirectionTracker()

    while True:
        ret, frame = cap.read()
        if not ret or (max_frames and frame_count >= max_frames):
            break

        frame_count += 1
        if frame_count % process_every_n != 0:
            continue

        processed_count += 1
        if callback:
            callback(int((frame_count / total_frames) * 100))

        # Детекция
        results = model.track(frame, classes=[2], verbose=False, conf=0.5, persist=True)

        frame_detections = []
        active_tracks = set()

        if (results[0].masks is not None and
                results[0].boxes is not None and
                results[0].boxes.id is not None):

            track_ids = results[0].boxes.id.cpu().numpy().astype(int)
            active_ids = set(track_ids)

            segments = results[0].masks.xyn
            boxes = results[0].boxes.xyxy.cpu().numpy()

            for i, (segment, track_id) in enumerate(zip(segments, track_ids)):
                if len(segment) < 3:
                    continue

                # Масштабируем точки
                segment_scaled = segment.copy()
                segment_scaled[:, 0] = segment[:, 0] * frame.shape[1]
                segment_scaled[:, 1] = segment[:, 1] * frame.shape[0]

                # Вычисляем центр
                center_x, center_y = calculate_enhanced_center(segment_scaled, boxes[i] if i < len(boxes) else None)
                center_2d = np.array([center_x, center_y])

                # Получаем направление
                direction = tracker.update(track_id, center_2d)
                active_tracks.add(track_id)

                frame_detections.append(CarDetection(
                    track_id=int(track_id),
                    center=center_2d,
                    direction=direction
                ))

            tracker.cleanup(active_tracks)

            # Добавляем в сцену
            timestamp = frame_count / fps
            scene.add_detections(frame_detections, processed_count, timestamp)

            if processed_count % 30 == 0:
                print(f"Обработано {processed_count} кадров")

    cap.release()
    return processed_count


# Для обратной совместимости
process_video_fast = process_video
