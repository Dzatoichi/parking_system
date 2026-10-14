"""Visual ordered vehicle handoff after registration completes on camera 2.

Run with: python run_ordered_search.py
Only the journey number is drawn above each matched vehicle. Re-ID and OCR are not used.
Cars leaving camera 2 receive numbers in exit order; on each topology handoff, the
same order is preserved for vehicles arriving from the same source camera.
"""
from __future__ import annotations

from collections import defaultdict, deque

import cv2
from ultralytics import YOLO

from Config import Config
from TopologyModule.CameraNetwork import CameraNetwork
from TopologyModule.TransitionTracker import CommandType, create_trackers


TILE_W, TILE_H = 640, 360
GRID_COLS = 3
WINDOW = "Ordered vehicle search (Q/Esc to quit)"


def main() -> None:
    network = CameraNetwork.from_yaml(Config.TOPOLOGY_CONFIG_PATH)
    camera_ids = list(network.camera_ids)
    trackers = create_trackers(network)
    captures = {}
    models = {}
    frame_ids = defaultdict(int)

    # FIFO of journey numbers waiting to enter each directed camera transition.
    waiting: dict[tuple[int, int], deque[int]] = defaultdict(deque)
    # Current camera-local track -> journey number.
    labels: dict[tuple[int, int], int] = {}
    next_number = 1

    for camera_id in camera_ids:
        source = Config.CAMERA_VIDEO_PATHS.get(camera_id, "")
        if not source:
            continue
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            print(f"[WARN] Cannot open camera {camera_id}: {source}")
            cap.release()
            continue
        captures[camera_id] = cap
        models[camera_id] = YOLO(Config.YOLO_CAR_MODEL_PATH)

    if 2 not in captures:
        raise RuntimeError(
            "Camera 2 video is not available. Configure PARKING_CAMERA_2_VIDEO "
            "or Config.CAMERA_VIDEO_PATHS[2]."
        )

    print("Waiting for registered cars to leave camera 2.")
    print("Numbers are assigned in camera-2 exit order; Re-ID/OCR are disabled.")

    try:
        while captures:
            tiles = {}
            for camera_id in camera_ids:
                if camera_id not in captures:
                    continue

                ok, raw = captures[camera_id].read()
                if not ok:
                    captures[camera_id].release()
                    del captures[camera_id]
                    continue

                frame = cv2.resize(raw, (1280, 720))
                result = models[camera_id].track(
                    frame,
                    persist=True,
                    tracker=Config.YOLO_TRACK_CONFIG_PATH,
                    conf=Config.YOLO_TRACK_CONF_THRESHOLD,
                    iou=Config.YOLO_TRACK_IOU_THRESHOLD,
                    verbose=False,
                )[0]

                if result.boxes is not None and result.boxes.id is not None:
                    boxes = result.boxes.xyxy.cpu().numpy()
                    ids = result.boxes.id.cpu().numpy().astype(int)
                    tracks = list(zip(ids, boxes))
                else:
                    boxes, ids, tracks = [], [], []

                commands = trackers[camera_id].update(frame_ids[camera_id], tracks)

                # Assign journey numbers when a registered vehicle exits camera 2.
                for command in commands:
                    pair = (command.source_camera, command.camera_id)
                    if command.type is CommandType.SEARCH_ON_CAMERA:
                        source_key = (command.source_camera, command.track_id)
                        journey_number = labels.pop(source_key, None)
                        if journey_number is None and command.source_camera == 2:
                            journey_number = next_number
                            next_number += 1
                            print(
                                f"[REGISTERED-EXIT] journey={journey_number} "
                                f"camera=2 track={command.track_id} "
                                f"next_camera={command.camera_id}"
                            )
                        if journey_number is not None:
                            waiting[pair].append(journey_number)

                    elif command.type is CommandType.MARK_ARRIVED:
                        queue = waiting[pair]
                        if queue:
                            journey_number = queue.popleft()
                            labels[(command.camera_id, command.track_id)] = journey_number
                            print(
                                f"[HANDOFF] journey={journey_number} "
                                f"camera={command.source_camera}->{command.camera_id} "
                                f"track={command.track_id}"
                            )

                display = frame.copy()
                for box, track_id in zip(boxes, ids):
                    journey_number = labels.get((camera_id, int(track_id)))
                    if journey_number is None:
                        continue
                    x1, y1, x2, y2 = map(int, box)
                    label = str(journey_number)
                    font = cv2.FONT_HERSHEY_SIMPLEX
                    scale, thickness = 1.0, 3
                    (tw, th), baseline = cv2.getTextSize(label, font, scale, thickness)
                    top = max(0, y1 - th - baseline - 8)
                    cv2.rectangle(display, (x1, top), (x1 + tw + 12, y1), (0, 0, 0), -1)
                    cv2.putText(
                        display, label, (x1 + 6, y1 - baseline - 4),
                        font, scale, (0, 255, 255), thickness, cv2.LINE_AA,
                    )

                # Draw topology transition lines only; no other annotations over tracks.
                for line in network.camera(camera_id).lines:
                    cv2.line(display, tuple(map(int, line.p1)), tuple(map(int, line.p2)),
                             (0, 0, 255), 2)

                tile = cv2.resize(display, (TILE_W, TILE_H))
                cv2.rectangle(tile, (0, 0), (TILE_W, 30), (20, 20, 20), -1)
                cv2.putText(tile, f"CAMERA {camera_id}", (10, 21),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2, cv2.LINE_AA)
                tiles[camera_id] = tile
                frame_ids[camera_id] += 1

            if not tiles:
                break

            rows = []
            for start in range(0, len(camera_ids), GRID_COLS):
                row_tiles = []
                for camera_id in camera_ids[start:start + GRID_COLS]:
                    row_tiles.append(
                        tiles.get(camera_id, cv2.resize(
                            cv2.cvtColor(
                                cv2.UMat(TILE_H, TILE_W, cv2.CV_8UC3).get(),
                                cv2.COLOR_BGR2RGB
                            ), (TILE_W, TILE_H)
                        ))
                    )
                if row_tiles:
                    rows.append(cv2.hconcat(row_tiles))
            if rows:
                cv2.imshow(WINDOW, cv2.vconcat(rows))
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
    finally:
        for cap in captures.values():
            cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
