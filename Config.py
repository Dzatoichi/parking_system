import os
from pathlib import Path

class Config:
    BASE_DIR = Path(__file__).parent

    DB_PARAMS = {
        'database': "parking_db",
        'user': "tracklet_manager",
        'password': "tracklet_manager",
        'host': "127.0.0.1",
        'port': "5432",
    }

    OSNET_MODEL_PATH = str(BASE_DIR / "Models/Tracking/OSNet/model_veri_1.pth")
    YOLO_PLATE_MODEL_PATH = str(BASE_DIR / "Models/PlateRecognition/YOLOv8/best.pt")
    YOLO_CAR_MODEL_PATH = str(BASE_DIR / "Models/Tracking/YOLOv11/yolo11m.pt")
    OCR_MODEL_PATH = str(BASE_DIR / "Models/PlateRecognition/OCR_CRNN/crnn_ocr_model_int8_fx.pth")

    DEVICE: str = "cpu"
