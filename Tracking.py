import cv2
from ultralytics import YOLO

from TrackletModule.TrackletManager import TrackletManager

# ===============================
# Конфигурация
# ===============================
VIDEO_PATH = "videos/ikit_2.mp4"
MODEL_PATH = "Models/Tracking/YOLOv11/yolo_35_epoches.pt"
OUTPUT_PATH = "output_ikit_2.avi"  # Путь для сохранения видео

CONF_THRES = 0.3
IOU_THRES = 0.7

TRACKER_CFG = "./vehicle_bytetrack_conf.yaml"

# ===============================
# Инициализация
# ===============================
# model = YOLO(MODEL_PATH)
model = YOLO("Models/Tracking/YOLOv11/yolo11m.pt")
cap = cv2.VideoCapture(VIDEO_PATH)

SHOW_VIDEO = False  # True - показывать на экране, False - только запись в файл

if not SHOW_VIDEO:
    # Инициализация VideoWriter для записи в файл
    output_size = (1280, 720)  # тот же размер, что и для отображения
    fourcc = cv2.VideoWriter_fourcc(*'XVID')  # кодек для AVI
    fps = 30  # примерный FPS (половина от исходного, т.к. пропускаем каждый второй кадр)
    out = cv2.VideoWriter(OUTPUT_PATH, fourcc, fps, output_size)

print(f"Запись видео в файл: {OUTPUT_PATH}")

traclet_manager = TrackletManager(
    cam_id=0,
    similarity_threshold=0.75,
    frames_for_confirm=3,
    frames_for_lost=5
)
traclet_manager.update_searched_vehicle(["14"])

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

    # ---------------------------
    # Обработка треков
    # ---------------------------

    traclet_manager.update(
        byte_track_bboxes=boxes,
        byte_track_ids=ids,
        frame_id=frame_id,
        frame=frame
    )

    for box, track_id in zip(boxes, ids):
        if track_id not in traclet_manager.t_storage.confirmed:
            continue
        x1, y1, x2, y2 = map(int, box)
        traclet = traclet_manager.t_storage.confirmed[track_id]

        label = f"veh_{traclet.vehicle_id}"
        # label = f"{track_id}"

        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.putText(
            frame,
            label,
            (x1, y1 - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2
        )

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
cv2.destroyAllWindows()

print(f"Видео сохранено в: {OUTPUT_PATH}")
print(f"Обработано кадров: {frame_id}")