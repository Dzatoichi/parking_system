"""Main controller: registration, camera transitions and FIFO journey tracking.

Run: python run_main_controller.py

The controller owns all video streams and all per-camera YOLO/BoT-SORT trackers.
Streams 2/3 are opened at the camera-1 registration trigger (like
run_feature_capture.py); other streams are opened lazily on a topology handoff and
seek to the source exit frame index. Journey numbers are assigned at registration
and carried through topology ENTER/EXIT events in FIFO order. Re-ID features and
OCR are collected during registration, but are not used to resolve handoffs yet.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np
import torch
from ultralytics import YOLO

from Config import Config
from FeaturesModule.FeaturesManager import FeaturesManager
from FeatureZoneModule import EntrySessionManager, FeatureZoneManager
from PlateOCRModule import PlateOCRTracker
from TopologyModule.CameraNetwork import CameraNetwork
from TopologyModule.TransitionTracker import CommandType, create_trackers


ROOT = Path(__file__).resolve().parent
ZONES_PATH = ROOT / "feature_zones.yaml"
TILE_SIZE = (640, 360)
WINDOW_NAME = "Parking main controller"
FEATURE_CAMERAS = (1, 2, 3)
INFERENCE_DEVICE = 0 if torch.cuda.is_available() else "cpu"


def source_for(camera_id: int) -> str:
    value = str(Config.CAMERA_VIDEO_PATHS.get(camera_id, "") or "").strip()
    if not value:
        raise ValueError(f"No video source configured for camera {camera_id}")
    path = Path(value).expanduser()
    return str(path if path.is_absolute() else ROOT / path)


def unpack_tracks(result):
    if result.boxes is None or result.boxes.id is None:
        return np.empty((0, 4), dtype=np.float32), np.empty((0,), dtype=int), []
    boxes = result.boxes.xyxy.cpu().numpy()
    ids = result.boxes.id.cpu().numpy().astype(int)
    return boxes, ids, [(int(tid), box.tolist()) for tid, box in zip(ids, boxes)]


def best_plate(votes: dict[str, list[float]]) -> tuple[str, float]:
    if not votes:
        return "UNKNOWN", 0.0
    plate, scores = max(votes.items(), key=lambda item: (sum(item[1]) / len(item[1]), len(item[1])))
    return plate, sum(scores) / len(scores)


def draw_journey_label(image, box, journey_number: int) -> None:
    x1, y1, _, _ = map(int, box)
    label = str(journey_number)
    font, scale, thickness = cv2.FONT_HERSHEY_SIMPLEX, 0.9, 2
    (tw, th), baseline = cv2.getTextSize(label, font, scale, thickness)
    top = max(0, y1 - th - baseline - 7)
    cv2.rectangle(image, (max(0, x1), top), (max(0, x1) + tw + 10, y1), (0, 0, 0), -1)
    cv2.putText(image, label, (max(0, x1) + 5, max(th + 2, y1 - baseline - 4)),
                font, scale, (0, 255, 255), thickness, cv2.LINE_AA)


def main() -> None:
    network = CameraNetwork.from_yaml(Config.TOPOLOGY_CONFIG_PATH)
    print("[CONTROLLER] Camera network:", network.camera_ids)
    for warning in network.warnings:
        print("[TOPOLOGY WARNING]", warning)

    # Reuse the existing registration components: feature galleries and OCR votes.
    features = FeaturesManager(Config.OSNET_MODEL_PATH)
    feature_managers = {
        cid: FeatureZoneManager(features, str(ZONES_PATH))
        for cid in FEATURE_CAMERAS
    }
    plate_ocr = PlateOCRTracker(
        plate_model_path=Config.YOLO_PLATE_MODEL_PATH,
        ocr_checkpoint_path=Config.OCR_MODEL_PATH,
        plate_conf=Config.OCR_PLATE_CONF_THRESHOLD,
        plate_iou=Config.OCR_PLATE_IOU_THRESHOLD,
        plate_imgsz=Config.OCR_PLATE_IMGSZ,
        ocr_device=Config.OCR_DEVICE,
        ocr_batch_size=Config.OCR_BATCH_SIZE,
        plate_device=INFERENCE_DEVICE,
    )

    sessions = EntrySessionManager()
    transition_trackers = create_trackers(network)
    captures: dict[int, cv2.VideoCapture] = {}
    models: dict[int, YOLO] = {}
    frame_ids: dict[int, int] = defaultdict(int)
    ended: set[int] = set()

    # Labels describe a journey, not a camera-local BoT-SORT ID.
    journey_by_track: dict[tuple[int, int], int] = {}
    session_by_journey: dict[int, str] = {}
    waiting: dict[tuple[int, int], list[tuple[int, str | None]]] = defaultdict(list)
    registered_tracks: set[tuple[int, int]] = set()
    plate_votes: dict[tuple[int, int], dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    feature_closed = Counter()
    registration_started = False
    registration_completed = False
    search_mode = False

    def open_camera(camera_id: int, seek_frame: int = 0) -> None:
        if camera_id in captures or camera_id in ended:
            return
        try:
            source = source_for(camera_id)
        except ValueError as exc:
            print(f"[STREAM ERROR] {exc}")
            return
        cap = cv2.VideoCapture(source)
        if not cap.isOpened():
            print(f"[STREAM ERROR] Cannot open camera {camera_id}: {source}")
            cap.release()
            ended.add(camera_id)
            return
        target_frame = max(0, int(seek_frame))
        if target_frame:
            cap.set(cv2.CAP_PROP_POS_FRAMES, target_frame)
        captures[camera_id] = cap
        models[camera_id] = YOLO(Config.YOLO_CAR_MODEL_PATH)
        frame_ids[camera_id] = target_frame
        print(f"[STREAM] camera={camera_id} opened at frame={target_frame}: {source}")

    def session_for_journey(journey_number: int) -> str | None:
        session_id = session_by_journey.get(journey_number)
        if not session_id:
            return None
        session = sessions.get_session(session_id)
        return session_id if session and session["status"] == "active" else None

    def start_registration(track_id: int, frame_id: int) -> None:
        nonlocal registration_started
        key = (1, int(track_id))
        if key in registered_tracks:
            return
        session = sessions.register_entry(1, int(track_id), int(frame_id))
        journey_number = session.entry_order
        registered_tracks.add(key)
        journey_by_track[key] = journey_number
        session_by_journey[journey_number] = session.session_id
        registration_started = True
        print(f"[REGISTER] journey={journey_number} camera=1 track={track_id} session={session.session_id}")
        # Registration view: keep the three capture cameras and camera 4 visible
        # as the first downstream/search camera. Each stream still has one owner.
        open_camera(2, frame_id)
        open_camera(3, frame_id)
        open_camera(4, frame_id)

    def finish_gallery(camera_id: int, track_id: int, journey_number: int | None) -> None:
        if camera_id not in FEATURE_CAMERAS:
            return
        gallery = feature_managers[camera_id].end_track(camera_id, int(track_id))
        if gallery is None:
            return
        feature_closed[camera_id] += 1
        session_id = session_for_journey(journey_number) if journey_number is not None else None
        if session_id:
            sessions.attach_gallery(session_id, camera_id, gallery)
        plate, confidence = best_plate(plate_votes.get((camera_id, int(track_id)), {}))
        print(
            f"[REGISTRATION DATA] journey={journey_number if journey_number is not None else '-'} "
            f"camera={camera_id} track={track_id} "
            f"features={len(gallery.get('original', [])) + len(gallery.get('flipped', []))} "
            f"plate={plate} ocr_conf={confidence:.2f}"
        )
        plate_votes.pop((camera_id, int(track_id)), None)

    open_camera(1, 0)
    if 1 not in captures:
        raise RuntimeError("Camera 1 could not be opened; controller cannot listen for registration triggers.")

    try:
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW_NAME, 1280, 720)
        print("[CONTROLLER] Waiting for a vehicle to enter the configured feature zone on camera 1. Q/Esc exits.")

        while captures:
            tiles: dict[int, np.ndarray] = {}
            # Snapshot avoids processing a newly opened stream twice in the same controller cycle.
            active_now = sorted(captures)
            for camera_id in active_now:
                if camera_id not in captures:
                    continue
                cap = captures[camera_id]
                ok, raw = cap.read()
                if not ok:
                    cap.release()
                    del captures[camera_id]
                    ended.add(camera_id)
                    print(f"[STREAM END] camera={camera_id}")
                    continue

                frame = cv2.resize(raw, (1280, 720))
                frame_id = frame_ids[camera_id]
                result = models[camera_id].track(
                    frame,
                    persist=True,
                    tracker=Config.YOLO_TRACK_CONFIG_PATH,
                    conf=Config.YOLO_TRACK_CONF_THRESHOLD,
                    iou=Config.YOLO_TRACK_IOU_THRESHOLD,
                    verbose=False,
                    device=INFERENCE_DEVICE,
                )[0]
                boxes, ids, tracks = unpack_tracks(result)
                visible_ids = [int(tid) for tid in ids]

                # Use the current registration-zone logic from run_feature_capture:
                # FeatureZoneManager activates a track when its configured anchor enters
                # feature_zones.yaml. No legacy TriggerModule ROI/area trigger is involved.
                active_ids = set()
                if camera_id in FEATURE_CAMERAS:
                    feature_managers[camera_id].process_frame(
                        camera_id, frame_id, frame, tracks
                    )
                    active_ids = {
                        tid for cam, tid in feature_managers[camera_id].active_track_keys()
                        if cam == camera_id
                    }
                    if camera_id == 1:
                        # Zone activation is the trigger; it is independent of the
                        # feature-sampling interval configured in FeatureZoneManager.
                        for tid in sorted(active_ids):
                            key = (1, int(tid))
                            if key not in registered_tracks:
                                start_registration(int(tid), frame_id)
                    if frame_id % max(1, Config.OCR_EVERY_N_FRAMES) == 0 and active_ids:
                        moving_tracks = [
                            (int(tid), box) for tid, box in zip(ids, boxes)
                            if int(tid) in active_ids
                        ]
                        for tid, reading in plate_ocr.recognize(frame, moving_tracks).items():
                            if reading.ocr_confidence >= Config.OCR_MIN_CHAR_CONFIDENCE:
                                plate_votes[(camera_id, int(tid))][reading.text].append(
                                    float(reading.ocr_confidence)
                                )

                commands = transition_trackers[camera_id].update(frame_id, tracks)
                exit_counts = Counter(
                    command.track_id for command in commands
                    if command.type is CommandType.SEARCH_ON_CAMERA
                )
                ambiguous_exit_tracks = {
                    track_id for track_id, count in exit_counts.items() if count > 1
                }
                for command in commands:
                    if (
                        command.type is CommandType.SEARCH_ON_CAMERA
                        and int(command.track_id) in ambiguous_exit_tracks
                    ):
                        targets = sorted(
                            item.camera_id for item in commands
                            if item.type is CommandType.SEARCH_ON_CAMERA
                            and item.track_id == command.track_id
                        )
                        print(
                            f"[AMBIGUOUS EXIT] camera={camera_id} track={command.track_id} "
                            f"simultaneous_targets={targets}; fix overlapping topology lines"
                        )
                        continue

                    if command.type is CommandType.SEARCH_ON_CAMERA:
                        source_key = (command.source_camera, int(command.track_id))
                        journey_number = journey_by_track.pop(source_key, None)
                        if journey_number is None:
                            continue
                        session_id = session_for_journey(journey_number)
                        pair = (command.source_camera, command.camera_id)
                        waiting[pair].append((journey_number, session_id))
                        finish_gallery(command.source_camera, command.track_id, journey_number)

                        # Registration is considered complete exactly at camera-2 EXIT.
                        if command.source_camera == 2:
                            completed = sessions.finish_on_camera2_track_lost(command.track_id)
                            if completed:
                                registration_completed = True
                                print(
                                    f"[REGISTRATION COMPLETE] journey={journey_number} "
                                    f"camera=2 track={command.track_id}"
                                )
                            else:
                                print(
                                    f"[SEARCH START] journey={journey_number} "
                                    f"camera=2 track={command.track_id} next_camera={command.camera_id}"
                                )
                        else:
                            print(
                                f"[HANDOFF TASK] journey={journey_number} "
                                f"{command.source_camera}->{command.camera_id}"
                            )
                        open_camera(command.camera_id, command.frame_id)

                    elif command.type is CommandType.MARK_ARRIVED:
                        pair = (command.source_camera, command.camera_id)
                        queue = waiting.get(pair, [])
                        if not queue:
                            continue
                        journey_number, session_id = queue.pop(0)
                        journey_by_track[(command.camera_id, int(command.track_id))] = journey_number
                        # Bind session tracks through the network while registration is active.
                        if session_id and command.camera_id in range(1, 10):
                            current = sessions.get_session(session_id)
                            if current and current["status"] == "active":
                                try:
                                    sessions.bind_track(session_id, command.camera_id, command.track_id)
                                except (KeyError, ValueError) as exc:
                                    print(f"[SESSION BIND WARNING] {exc}")
                        print(
                            f"[CANDIDATE FIFO] journey={journey_number} "
                            f"{command.source_camera}->{command.camera_id} "
                            f"local_track={command.track_id}"
                        )

                # Keep feature gallery closure in sync if the track was lost without an EXIT.
                if camera_id in FEATURE_CAMERAS:
                    visible_set = set(visible_ids)
                    for (cam, track_id), journey_number in list(journey_by_track.items()):
                        if cam == camera_id and track_id not in visible_set:
                            # A temporary detector dropout is not enough to declare a transition.
                            # CrossingDetector owns the definitive EXIT event; do not close here.
                            pass

                display = frame.copy()
                for box, track_id in zip(boxes, ids):
                    track_id = int(track_id)
                    x1, y1, x2, y2 = map(int, box)
                    journey_number = journey_by_track.get((camera_id, track_id))
                    color = (0, 220, 0) if journey_number is not None else (185, 185, 185)
                    cv2.rectangle(display, (x1, y1), (x2, y2), color, 2)
                    if journey_number is not None:
                        draw_journey_label(display, box, journey_number)

                # Show the actual configured topology lines, which are the movement signals.
                for line in network.camera(camera_id).lines:
                    p1, p2 = tuple(map(int, line.p1)), tuple(map(int, line.p2))
                    cv2.line(display, p1, p2, (0, 0, 255), 2)

                tile = cv2.resize(display, TILE_SIZE)
                cv2.rectangle(tile, (0, 0), (TILE_SIZE[0], 30), (20, 20, 20), -1)
                phase = (
                    "SEARCH / DOWNSTREAM CAMERAS" if search_mode
                    else "REGISTRATION + CAMERA 4 SEARCH VIEW" if registration_started
                    else "WAITING FOR FEATURE ZONE"
                )
                cv2.putText(tile, f"CAM {camera_id} | {phase}", (10, 21),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)
                tiles[camera_id] = tile
                frame_ids[camera_id] += 1

            if not tiles:
                break

            # Switch the UI and stream set only after every registered session has
            # completed its camera-2 registration leg. Keep downstream streams (4-9)
            # and any lazily opened search targets; remove registration cameras 1-3.
            if registration_completed and not sessions.active_sessions() and not search_mode:
                search_mode = True
                for registration_camera in FEATURE_CAMERAS:
                    cap = captures.pop(registration_camera, None)
                    if cap is not None:
                        cap.release()
                    models.pop(registration_camera, None)
                    print(f"[SEARCH VIEW] removed registration camera {registration_camera}")
                print("[SEARCH VIEW] registration finished; showing downstream/search cameras only")

            if search_mode:
                # Display only downstream cameras currently carrying a registered
                # journey or awaited by a handoff task, not every camera ever opened.
                journey_cameras = {
                    camera_id for camera_id, _track_id in journey_by_track
                    if camera_id not in FEATURE_CAMERAS
                }
                awaited_cameras = {
                    target_camera
                    for (_source_camera, target_camera), queue in waiting.items()
                    if queue and target_camera not in FEATURE_CAMERAS
                }
                relevant_cameras = journey_cameras | awaited_cameras
                tiles = {
                    cid: tile for cid, tile in tiles.items()
                    if cid not in FEATURE_CAMERAS and cid in relevant_cameras
                }
                if not tiles and captures:
                    # A handoff may have just opened its target; wait for its first frame.
                    continue
            ordered_ids = sorted(tiles)
            columns = 3
            cell_width, cell_height = TILE_SIZE
            rows = []
            for offset in range(0, len(ordered_ids), columns):
                row_tiles = [tiles[cid] for cid in ordered_ids[offset:offset + columns]]
                # Pad the last row so every row has the same width for vconcat.
                while len(row_tiles) < columns:
                    row_tiles.append(
                        np.zeros((cell_height, cell_width, 3), dtype=np.uint8)
                    )
                rows.append(cv2.hconcat(row_tiles))
            if rows:
                cv2.imshow(WINDOW_NAME, cv2.vconcat(rows))
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
    finally:
        for cap in captures.values():
            cap.release()
        cv2.destroyAllWindows()
        for camera_id, manager in feature_managers.items():
            for (cam, track_id), gallery in manager.close_all().items():
                print(
                    f"[SHUTDOWN GALLERY] camera={cam} track={track_id} "
                    f"samples={len(gallery.get('original', [])) + len(gallery.get('flipped', []))}"
                )
        print("[CONTROLLER] Closed streams. Feature galleries closed:", dict(feature_closed))


if __name__ == "__main__":
    main()
