import cv2
from ultralytics import YOLO

from Config import Config
from PlateRecognitionModule.core.PlateRecognizer import PlateRecognizer

plate_rec = PlateRecognizer()

# ===============================
# Конфигурация
# ===============================
VIDEO_PATH = "../videos/short_front_left.mp4"
OUTPUT_PATH = "output_ikit_2.avi"  # Путь для сохранения видео

CONF_THRES = 0.3
IOU_THRES = 0.7

TRACKER_CFG = "../vehicle_bytetrack_conf.yaml"

# ===============================
# Инициализация
# ===============================
# model = YOLO(MODEL_PATH)
model = YOLO(Config.YOLO_CAR_MODEL_PATH)
cap = cv2.VideoCapture(VIDEO_PATH)

SHOW_VIDEO = True  # True - показывать на экране, False - только запись в файл

if not SHOW_VIDEO:
    # Инициализация VideoWriter для записи в файл
    output_size = (1280, 720)  # тот же размер, что и для отображения
    fourcc = cv2.VideoWriter_fourcc(*'XVID')  # кодек для AVI
    fps = 30  # примерный FPS (половина от исходного, т.к. пропускаем каждый второй кадр)
    out = cv2.VideoWriter(OUTPUT_PATH, fourcc, fps, output_size)
    print(f"Запись видео в файл: {OUTPUT_PATH}")

# ===============================
# Основной цикл
# ===============================

frame_id = 0
frame_counter_for_fps = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break

    if frame_counter_for_fps != 1:
        frame_counter_for_fps = 1
        continue

    frame_counter_for_fps = 0

    frame = cv2.resize(frame, (1280, 720))

    H, W = frame.shape[:2]

    # ---------------------------
    # YOLO + ByteTrack
    # ---------------------------
    results = model.track(
        frame,
        classes=[2],
        persist=True,
        tracker=TRACKER_CFG,
        conf=CONF_THRES,
        iou=IOU_THRES,
        verbose=False
    )

    r = results[0]

    if r.boxes is None or r.boxes.id is None:
        # Показываем на экране
        cv2.imshow("Tracking", frame)
        # Записываем в файл
        out.write(frame)

        if cv2.waitKey(1) == 27:
            break
        continue

    boxes = r.boxes.xyxy.cpu().numpy()
    ids = r.boxes.id.cpu().numpy().astype(int)

    for box, track_id in zip(boxes, ids):
        x1, y1, x2, y2 = map(int, box)

        crop_car = frame[y1:y2, x1:x2]
        detections = plate_rec.process_frame(crop_car)

        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(
            frame,
            f"car {track_id}",
            (x1, y1 - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2
        )

        for res in detections:
            px1, py1, px2, py2 = res['bbox']
            text = res.get('text', '')
            cv2.rectangle(crop_car, (px1, py1), (px2, py2), (0, 0, 255), 2)
            cv2.putText(frame, text, (x2 - 110, y1 - 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    if SHOW_VIDEO:
        cv2.imshow("Tracking", frame)
    else:
        # Записываем в файл
        out.write(frame)

    if SHOW_VIDEO and cv2.waitKey(1) == 27:
        break

    frame_id += 1

cap.release()
if not SHOW_VIDEO:
    out.release()  # Важно: закрываем файл записи
    print(f"Видео сохранено в: {OUTPUT_PATH}")
    print(f"Обработано кадров: {frame_id}")

cv2.destroyAllWindows()
