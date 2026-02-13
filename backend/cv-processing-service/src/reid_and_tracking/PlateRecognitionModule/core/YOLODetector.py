from typing import List, Dict, Any
import torch
from ultralytics import YOLO
import numpy as np


class YOLODetector:
    """Обертка для модели детекции YOLO."""

    DETECTION_CONFIDENCE_THRESHOLD: float = 0.5

    def __init__(self, model_path: str, device: str):
        self.model = YOLO(model_path)
        device = torch.device(device)
        self.model.to(device)
        self.device = device
        print("✅ Детектор YOLO успешно загружен.")

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """Обнаруживает номера на ОДНОМ кадре (для изображений)."""
        detections = self.model.predict(frame, verbose=False, device=self.device)
        results = []
        for det in detections[0].boxes.data:
            x1, y1, x2, y2, conf, _ = det.cpu().numpy()
            if conf >= YOLODetector.DETECTION_CONFIDENCE_THRESHOLD:
                results.append({"bbox": [int(x1), int(y1), int(x2), int(y2)], "confidence": float(conf)})
        return results
