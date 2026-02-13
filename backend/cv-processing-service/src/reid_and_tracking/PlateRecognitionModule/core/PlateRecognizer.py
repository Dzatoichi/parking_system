from typing import List, Dict, Any
import numpy as np

from Config import Config
from PlateRecognitionModule.core.CRNN import CRNNRecognizer
from PlateRecognitionModule.core.YOLODetector import YOLODetector
import PlateRecognitionModule.core.utils as utils


class PlateRecognizer:
    """Главный класс, управляющий процессом распознавания."""

    def __init__(self):
        self.detector = YOLODetector(Config.YOLO_PLATE_MODEL_PATH, device=Config.DEVICE)
        self.recognizer = CRNNRecognizer(Config.OCR_MODEL_PATH, device=Config.DEVICE)

    def process_frame(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        detections = self.detector.detect(frame=frame)
        for detection in detections:
            x1, y1, x2, y2 = detection['bbox']
            roi = frame[y1:y2, x1:x2]

            if roi.size > 0:
                # 1. УЛУЧШАЕМ ПРЕПРОЦЕССИНГ
                processed_plate = utils.preprocess_plate(roi)
            else:
                continue

            if processed_plate.size > 0:
                # 2. РАСПОЗНАЕМ
                current_text = self.recognizer.recognize(processed_plate)
                detection['text'] = current_text
        return detections
