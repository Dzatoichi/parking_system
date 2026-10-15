"""Nine-camera controller: camera-1 registration gallery, downstream Re-ID and topology handoffs.

Camera 1 assigns global identities, reads plates and builds the initial Re-ID gallery,
but does not participate in downstream topology tracking. Camera 2 binds scan entries
by the configured scan FIFO and also contributes gallery features; cameras 2-9 track
routes using topology handoffs and moving-track Re-ID. OCR runs on camera 1 only.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import json
import time
from pathlib import Path

import cv2
import numpy as np
import torch
from ultralytics import YOLO

from Config import Config
from FeaturesModule.FeaturesManager import FeaturesManager
from FeatureZoneModule import EntrySessionManager, FeatureZoneManager
from PlateOCRModule import PlateOCRTracker
from DB.parking_repository import ParkingRepository
from RuntimeReID import RuntimeReID
from TopologyModule.CameraNetwork import CameraNetwork
from TopologyModule.TransitionTracker import CommandType, create_trackers


ROOT = Path(__file__).resolve().parent
ZONES_PATH = ROOT / "feature_zones.yaml"
TILE_SIZE = (640, 360)
WINDOW_NAME = "Parking main controller"
REPORT_PATH = ROOT / "main_controller_run_report.json"
SCAN_CAMERAS = (1, 2, 3)
FEATURE_CAMERAS = SCAN_CAMERAS
GALLERY_CAMERAS = (1, 2, 3)
OCR_CAMERAS = (1,)
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


def draw_text_label(image, box, label: str, color) -> None:
    x1, y1, _, _ = map(int, box)
    font, scale, thickness = cv2.FONT_HERSHEY_SIMPLEX, 0.65, 2
    (tw, th), baseline = cv2.getTextSize(label, font, scale, thickness)
    text_y = max(th + baseline + 4, y1 - 7)
    bg_x1, bg_y1 = max(0, x1), max(0, text_y - th - baseline - 4)
    bg_x2 = min(image.shape[1] - 1, bg_x1 + tw + 10)
    bg_y2 = min(image.shape[0] - 1, text_y + baseline + 3)
    cv2.rectangle(image, (bg_x1, bg_y1), (bg_x2, bg_y2), (0, 0, 0), -1)
    cv2.putText(image, label, (bg_x1 + 5, text_y), font, scale, color, thickness, cv2.LINE_AA)


def main() -> None:
    started_at = time.time()
    reid_matches: list[dict] = []
    reid_expired: list[dict] = []
    database = ParkingRepository() if Config.DB_ENABLED else None
    if database is not None:
        try:
            database.connect()
        except Exception as exc:
            raise RuntimeError(
                "PostgreSQL connection failed. Start PostgreSQL/PGlite's PostgreSQL-wire "
                "server and configure PARKING_DB_HOST, PARKING_DB_PORT, PARKING_DB_NAME, "
                "PARKING_DB_USER and PARKING_DB_PASSWORD."
            ) from exc
        print("[DATABASE] PostgreSQL connected; schema ready (JSONB embeddings, no pgvector).")
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
    runtime_reid = RuntimeReID(
        features,
        threshold=Config.REID_SIMILARITY_THRESHOLD,
        sample_every=max(1, int(getattr(Config, "RUNTIME_REID_EVERY_N_FRAMES", 5))),
        min_samples=max(1, int(getattr(Config, "RUNTIME_REID_MIN_SAMPLES", 2))),
    )
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
    camera_times: dict[int, float] = defaultdict(float)
    ended: set[int] = set()
    trigger_skip_frames = max(1, int(getattr(Config, "TRIGGER_SKIP_FRAMES", 3)))

    # Labels describe a journey, not a camera-local BoT-SORT ID.
    journey_by_track: dict[tuple[int, int], int] = {}
    session_by_journey: dict[int, str] = {}
    pending_reid: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    registered_tracks: set[tuple[int, int]] = set()
    plate_votes: dict[tuple[int, int], dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    journey_plate_votes: dict[int, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    feature_closed = Counter()
    registration_completed = False
    search_mode = False
    scan_pending: list[tuple[int, str, int]] = []
    last_centers: dict[tuple[int, int], tuple[float, float]] = {}
    movement_scores: dict[tuple[int, int], float] = {}
    movement_state: dict[tuple[int, int], bool] = {}
    movement_last_seen: dict[tuple[int, int], int] = {}
    track_last_seen: dict[tuple[int, int], int] = {}
    camera2_interior_seen: set[tuple[int, int]] = set()
    camera2_feature_closed_tracks: set[tuple[int, int]] = set()

    def open_camera(camera_id: int, seek_seconds: float = 0.0) -> None:
        """Open a stream only when a trigger/search task needs it.

        Video files are assumed to share a recording timeline. Seek by timestamp,
        not by copying another camera's frame index (FPS can differ).
        """
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
        target_seconds = max(0.0, float(seek_seconds))
        if target_seconds > 0:
            cap.set(cv2.CAP_PROP_POS_MSEC, target_seconds * 1000.0)
        captures[camera_id] = cap
        models[camera_id] = YOLO(Config.YOLO_CAR_MODEL_PATH)
        fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        target_frame = max(0, int(cap.get(cv2.CAP_PROP_POS_FRAMES) or 0))
        frame_ids[camera_id] = target_frame
        camera_times[camera_id] = target_seconds
        print(
            f"[STREAM] lazy-open camera={camera_id} at ~{target_seconds:.2f}s "
            f"(frame={target_frame}, fps={fps:.2f}): {source}"
        )

    def session_for_journey(journey_number: int) -> str | None:
        session_id = session_by_journey.get(journey_number)
        if not session_id:
            return None
        session = sessions.get_session(session_id)
        return session_id if session and session["status"] == "active" else None

    def start_registration(track_id: int, frame_id: int) -> None:
        key = (1, int(track_id))
        if key in registered_tracks:
            return
        session = sessions.register_entry(1, int(track_id), int(frame_id))
        journey_number = database.create_vehicle(1, int(track_id), int(frame_id)) if database is not None else session.entry_order
        registered_tracks.add(key)
        journey_by_track[key] = journey_number
        session_by_journey[journey_number] = session.session_id
        trigger_time = camera_times.get(1, 0.0)
        # Registration trigger wakes only the three scan cameras. The remaining
        # cameras stay closed until a topology EXIT creates a search task.
        open_camera(2, trigger_time)
        open_camera(3, trigger_time)
        # Store the actual target-camera frame after timestamp seeking, otherwise
        # the FIFO TTL would be measured from frame zero and could expire instantly.
        scan_pending.append((journey_number, session.session_id, frame_ids.get(2, 0)))
        print(f"[REGISTER] global_id={journey_number} camera=1 scan_track={track_id} session={session.session_id}")
        print(f"[SCAN ACTIVATION] cameras=1,2,3 trigger_time={trigger_time:.2f}s")

    def finish_gallery(camera_id: int, track_id: int, journey_number: int | None) -> None:
        if camera_id not in FEATURE_CAMERAS:
            return
        gallery = feature_managers[camera_id].end_track(camera_id, int(track_id))
        feature_count = 0
        if gallery is not None:
            feature_closed[camera_id] += 1
            feature_count = len(gallery.get("original", [])) + len(gallery.get("flipped", []))
            if journey_number is not None and camera_id in GALLERY_CAMERAS:
                runtime_reid.add_identity_gallery(int(journey_number), gallery)
                if database is not None:
                    for mirrored, key_name in ((False, "original"), (True, "flipped")):
                        for vector in gallery.get(key_name, []):
                            database.save_embedding(journey_number, camera_id, track_id, frame_id, vector, mirrored)
            session_id = session_for_journey(journey_number) if journey_number is not None else None
            if session_id:
                sessions.attach_gallery(session_id, camera_id, gallery)
        local_votes = plate_votes.get((camera_id, int(track_id)), {})
        if journey_number is not None:
            for text, scores in local_votes.items():
                journey_plate_votes[int(journey_number)][text].extend(scores)
            plate, confidence = best_plate(journey_plate_votes[int(journey_number)])
        else:
            plate, confidence = best_plate(local_votes)
        print(
            f"[REGISTRATION DATA] journey={journey_number if journey_number is not None else '-'} "
            f"camera={camera_id} track={track_id} features={feature_count} "
            f"plate={plate} ocr_conf={confidence:.2f}"
        )
        plate_votes.pop((camera_id, int(track_id)), None)

    # Only camera 1 is open initially, acting as a lightweight trigger.
    # Scan cameras 2-3 and route cameras 4-9 are opened on demand.
    open_camera(1, 0.0)
    if 1 not in captures:
        if database is not None:
            database.close()
        raise RuntimeError("Camera 1 could not be opened; controller cannot listen for registration triggers.")

    try:
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW_NAME, 1280, 720)
        print(
            f"[CONTROLLER] Lazy mode: idle camera 1 skips {trigger_skip_frames - 1} "
            "frames between trigger inferences; active journeys use every frame; cameras 2-9 open on demand. Q/Esc exits."
        )

        while captures:
            tiles: dict[int, np.ndarray] = {}
            # Snapshot avoids processing a newly opened stream twice in the same controller cycle.
            active_now = sorted(captures)
            for camera_id in active_now:
                if camera_id not in captures:
                    continue
                cap = captures[camera_id]
                # While no vehicle journey/search is active, camera 1 is a lightweight
                # trigger: read every source frame but infer only every Nth frame.
                system_busy = bool(journey_by_track or scan_pending or any(pending_reid.values()))
                if camera_id == 1 and not system_busy and frame_ids[1] % trigger_skip_frames != 0:
                    ok, _skipped_raw = cap.read()
                    if not ok:
                        cap.release()
                        del captures[camera_id]
                        ended.add(camera_id)
                        print(f"[STREAM END] camera={camera_id}")
                        continue
                    frame_ids[camera_id] += 1
                    camera_times[camera_id] = float(cap.get(cv2.CAP_PROP_POS_MSEC) or 0.0) / 1000.0
                    continue
                ok, raw = cap.read()
                if not ok:
                    cap.release()
                    del captures[camera_id]
                    ended.add(camera_id)
                    print(f"[STREAM END] camera={camera_id}")
                    continue

                camera_times[camera_id] = float(cap.get(cv2.CAP_PROP_POS_MSEC) or 0.0) / 1000.0
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
                for visible_track_id in visible_ids:
                    track_last_seen[(camera_id, int(visible_track_id))] = frame_id
                sampled_embeddings = []
                newly_bound_tracks: set[tuple[int, int]] = set()
                moving_tracks = []
                if camera_id != 1:
                    for track_id, bbox in tracks:
                        x1, y1, x2, y2 = map(float, bbox)
                        center = ((x1 + x2) / 2.0, (y1 + y2) / 2.0)
                        object_size = max(1.0, ((x2 - x1) + (y2 - y1)) / 2.0)
                        key = (camera_id, int(track_id))
                        previous = last_centers.get(key)
                        if previous is None:
                            smoothed_center = center
                            score = 0.0
                        else:
                            alpha = float(Config.TRACKER_MOVEMENT_ALFA)
                            smoothed_center = (
                                alpha * center[0] + (1.0 - alpha) * previous[0],
                                alpha * center[1] + (1.0 - alpha) * previous[1],
                            )
                            score = (
                                ((smoothed_center[0] - previous[0]) ** 2
                                 + (smoothed_center[1] - previous[1]) ** 2) ** 0.5
                            ) / object_size
                        last_centers[key] = smoothed_center
                        movement_scores[key] = score
                        movement_last_seen[key] = frame_id
                        is_moving = (
                            object_size >= Config.TRACKER_MOVEMENT_MIN_SIZE
                            and score >= Config.TRACKER_MOVEMENT_THRESHOLD
                        )
                        old_state = movement_state.get(key)
                        movement_state[key] = is_moving
                        if old_state is not None and old_state != is_moving and database is not None:
                            database.record_event(
                                camera_id, track_id, frame_id,
                                "movement_started" if is_moving else "movement_stopped",
                                global_id=journey_by_track.get(key), movement_state="moving" if is_moving else "stationary",
                                bbox=bbox, details={"normalized_displacement": float(score)},
                            )
                        if is_moving:
                            moving_tracks.append((int(track_id), bbox))
                    if camera_id == 2 and camera2_feature_closed_tracks:
                        moving_tracks = [
                            item for item in moving_tracks
                            if (2, int(item[0])) not in camera2_feature_closed_tracks
                        ]
                    sampled_embeddings = runtime_reid.update_camera(
                        camera_id, frame_id, frame, moving_tracks
                    )

                # Use the current registration-zone logic from run_feature_capture:
                # FeatureZoneManager activates a track when its configured anchor enters
                # feature_zones.yaml. No legacy TriggerModule ROI/area trigger is involved.
                active_ids = set()
                if camera_id in FEATURE_CAMERAS:
                    # Camera 1 builds the initial appearance gallery as well as triggering
                    # registration/OCR. It is excluded only from downstream topology events.
                    # Cameras 2 and 3 also build galleries and remain active route cameras.
                    feature_managers[camera_id].process_frame(
                        camera_id, frame_id, frame, tracks
                    )
                    active_ids = {
                        tid for cam, tid in feature_managers[camera_id].active_track_keys()
                        if cam == camera_id
                    }
                    if camera_id == 2:
                        # FIFO is permitted only between the scan station and the
                        # useful overview camera. It is never used on cameras 4-9.
                        fifo_ttl = max(1, int(getattr(Config, "SCAN_FIFO_TTL_FRAMES", 900)))
                        fresh_scan_queue = []
                        for pending_global_id, pending_session_id, created_camera2_frame in scan_pending:
                            if frame_id - created_camera2_frame > fifo_ttl:
                                print(f"[SCAN FIFO EXPIRED] global_id={pending_global_id} waited_frames={frame_id - created_camera2_frame}")
                                if database is not None:
                                    database.record_event(
                                        2, -1, frame_id, "scan_fifo_expired",
                                        global_id=pending_global_id, source_camera_id=1, target_camera_id=2,
                                        details={"target_frames_waited": int(frame_id - created_camera2_frame)},
                                    )
                            else:
                                fresh_scan_queue.append((pending_global_id, pending_session_id, created_camera2_frame))
                        scan_pending[:] = fresh_scan_queue
                        for scan_track_id in sorted(active_ids):
                            key = (2, int(scan_track_id))
                            if key in journey_by_track or not scan_pending:
                                continue
                            global_id, session_id, _created_camera2_frame = scan_pending.pop(0)
                            journey_by_track[key] = global_id
                            newly_bound_tracks.add(key)
                            try:
                                sessions.bind_track(session_id, 2, int(scan_track_id))
                            except (KeyError, ValueError) as exc:
                                print(f"[SCAN FIFO WARNING] {exc}")
                            if database is not None:
                                database.record_event(
                                    2, int(scan_track_id), frame_id, "scan_zone_fifo_bind",
                                    global_id=global_id, source_camera_id=1, target_camera_id=2,
                                    movement_state="moving" if movement_state.get(key, False) else "stationary",
                                )
                                for vector in runtime_reid.track_features.get(key, []):
                                    database.save_embedding(global_id, 2, int(scan_track_id), frame_id, vector)
                            print(f"[SCAN FIFO] global_id={global_id} camera=1->2 local_track={scan_track_id}")
                    if camera_id == 2:
                        # Run after FIFO binding so a gallery closed at the frame
                        # edge can still be saved under the correct global identity.
                        frame_h, frame_w = frame.shape[:2]
                        for seen_track_id, seen_bbox in tracks:
                            seen_key = (2, int(seen_track_id))
                            sx1, sy1, sx2, sy2 = map(float, seen_bbox)
                            touches_edge = (
                                sx1 <= 1.0 or sy1 <= 1.0
                                or sx2 >= frame_w - 2.0 or sy2 >= frame_h - 2.0
                            )
                            if not touches_edge:
                                camera2_interior_seen.add(seen_key)
                            elif seen_track_id in active_ids and seen_key in camera2_interior_seen:
                                finish_gallery(
                                    2, int(seen_track_id),
                                    journey_by_track.get(seen_key),
                                )
                                # Stop both scan-gallery and runtime Re-ID sampling
                                # for this camera-local track after frame exit.
                                camera2_feature_closed_tracks.add(seen_key)
                                runtime_reid.forget_track(2, int(seen_track_id))
                                camera2_interior_seen.discard(seen_key)
                                print(
                                    f"[SCAN GALLERY CLOSED] camera=2 track={seen_track_id} "
                                    f"reason=frame_exit frame={frame_id}"
                                )
                    if camera_id == 1:
                        # Zone activation is the trigger; it is independent of the
                        # feature-sampling interval configured in FeatureZoneManager.
                        for tid in sorted(active_ids):
                            key = (1, int(tid))
                            if key not in registered_tracks:
                                start_registration(int(tid), frame_id)
                    if camera_id in OCR_CAMERAS and frame_id % max(1, Config.OCR_EVERY_N_FRAMES) == 0 and active_ids:
                        moving_tracks = [
                            (int(tid), box) for tid, box in zip(ids, boxes)
                            if int(tid) in active_ids
                        ]
                        for tid, reading in plate_ocr.recognize(frame, moving_tracks).items():
                            if reading.ocr_confidence >= Config.OCR_MIN_CHAR_CONFIDENCE:
                                plate_votes[(camera_id, int(tid))][reading.text].append(
                                    float(reading.ocr_confidence)
                                )
                                global_id = journey_by_track.get((camera_id, int(tid)))
                                if global_id is not None:
                                    journey_plate_votes[int(global_id)][reading.text].append(float(reading.ocr_confidence))
                                    if database is not None:
                                        database.update_plate(
                                            global_id, camera_id, int(tid), frame_id, reading.text,
                                            reading.ocr_confidence, reading.plate_confidence, reading.subtype,
                                        )

                # Camera 1 is a plate-scanning station, not a topology node. Its poor
                # overview must not create downstream handoff tasks.
                # Persist new moving-track embeddings after the scan-zone binding check.
                if database is not None:
                    for sampled_track_id, vector in sampled_embeddings:
                        global_id = journey_by_track.get((camera_id, int(sampled_track_id)))
                        if global_id is not None and (camera_id, int(sampled_track_id)) not in newly_bound_tracks:
                            database.save_embedding(global_id, camera_id, sampled_track_id, frame_id, vector)
                commands = transition_trackers[camera_id].update(frame_id, tracks) if camera_id != 1 else []
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
                        # A topology EXIT creates a search task: lazily open only its
                        # destination camera, aligned to the source video's timestamp.
                        target_time = camera_times.get(command.source_camera, 0.0)
                        open_camera(command.camera_id, target_time)
                        finish_gallery(command.source_camera, command.track_id, journey_number)
                        # Camera 1 has no topology transitions. Every actual network handoff
                        # (cameras 2-9) must pass topology eligibility AND Re-ID.
                        if command.source_camera not in GALLERY_CAMERAS:
                            runtime_reid.extend_identity(
                                journey_number, command.source_camera, command.track_id
                            )
                        pending_reid[pair].append(
                            (journey_number, frame_ids.get(command.camera_id, 0))
                        )
                        if database is not None:
                            database.record_event(
                                command.source_camera, command.track_id, command.frame_id,
                                "topology_exit", global_id=journey_number,
                                source_camera_id=command.source_camera, target_camera_id=command.camera_id,
                                movement_state="moving",
                            )
                        # Source track embeddings are no longer needed once handed off.
                        runtime_reid.forget_track(command.source_camera, command.track_id)

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
                        # Target stream is already active; never start/seek it on a handoff.

                    elif command.type is CommandType.MARK_ARRIVED:
                        # ENTER merely makes this local track eligible for the source
                        # camera's pending task. Identity assignment happens below via Re-ID.
                        if database is not None:
                            database.record_event(
                                command.camera_id, command.track_id, command.frame_id,
                                "topology_enter", source_camera_id=command.source_camera,
                                target_camera_id=command.camera_id,
                                movement_state="moving" if movement_state.get((command.camera_id, int(command.track_id)), False) else "stationary",
                                bbox=next((box for tid, box in tracks if int(tid) == int(command.track_id)), None),
                            )
                        print(
                            f"[REID CANDIDATE GATE] {command.source_camera}->{command.camera_id} "
                            f"local_track={command.track_id}; waiting for moving-track appearance match"
                        )

                # Resolve only topology-eligible destination tracks against pending journeys.
                # A target track must have crossed an ENTER line from this exact source camera.
                for (source_camera, target_camera), pending_items in list(pending_reid.items()):
                    if target_camera != camera_id or not pending_items:
                        continue
                    ttl = max(1, int(getattr(Config, "RUNTIME_REID_PENDING_TTL_FRAMES", 900)))
                    active_items = []
                    for journey_id, created_target_frame in pending_items:
                        if frame_id - created_target_frame > ttl:
                            expired_record = {
                                "journey_id": int(journey_id),
                                "source_camera": int(source_camera),
                                "target_camera": int(target_camera),
                                "target_frames_waited": int(frame_id - created_target_frame),
                            }
                            reid_expired.append(expired_record)
                            if database is not None:
                                database.record_event(
                                    target_camera, -1, frame_id, "reid_handoff_expired",
                                    global_id=journey_id, source_camera_id=source_camera,
                                    target_camera_id=target_camera,
                                    details={"target_frames_waited": int(frame_id - created_target_frame)},
                                )
                            print(
                                f"[REID EXPIRED] journey={journey_id} "
                                f"{source_camera}->{target_camera} after {frame_id - created_target_frame} target frames"
                            )
                        else:
                            active_items.append((journey_id, created_target_frame))
                    pending_items[:] = active_items
                    if not pending_items:
                        pending_reid.pop((source_camera, target_camera), None)
                        continue
                    journey_ids = [journey_id for journey_id, _ in pending_items]
                    candidate_ids = transition_trackers[camera_id].tracks_arrived_from(source_camera)
                    scored = []
                    for candidate_id in candidate_ids:
                        if (camera_id, int(candidate_id)) in journey_by_track:
                            continue
                        if not movement_state.get((camera_id, int(candidate_id)), False):
                            continue
                        for journey_id in journey_ids:
                            score = runtime_reid.match_track_to_journey(
                                camera_id, int(candidate_id), int(journey_id)
                            )
                            if score is not None:
                                scored.append((float(score), int(journey_id), int(candidate_id)))
                    used_journeys, used_tracks = set(), set()
                    for score, journey_id, candidate_id in sorted(scored, reverse=True):
                        if journey_id in used_journeys or candidate_id in used_tracks:
                            continue
                        journey_by_track[(camera_id, candidate_id)] = journey_id
                        if database is not None and camera_id not in GALLERY_CAMERAS:
                            for vector in runtime_reid.track_features.get((camera_id, candidate_id), []):
                                database.save_embedding(journey_id, camera_id, candidate_id, frame_id, vector)
                        session_id = session_by_journey.get(journey_id)
                        if session_id:
                            current = sessions.get_session(session_id)
                            if current and current["status"] == "active":
                                try:
                                    sessions.bind_track(session_id, camera_id, candidate_id)
                                except (KeyError, ValueError) as exc:
                                    print(f"[SESSION BIND WARNING] {exc}")
                        pending_items[:] = [
                            item for item in pending_items if item[0] != journey_id
                        ]
                        used_journeys.add(journey_id)
                        used_tracks.add(candidate_id)
                        if database is not None:
                            database.record_event(
                                target_camera, candidate_id, frame_id, "reid_match",
                                global_id=journey_id, source_camera_id=source_camera,
                                target_camera_id=target_camera, movement_state="moving", score=score,
                            )
                        reid_matches.append({
                            "journey_id": int(journey_id),
                            "source_camera": int(source_camera),
                            "target_camera": int(target_camera),
                            "target_track_id": int(candidate_id),
                            "cosine_similarity": float(score),
                        })
                        print(
                            f"[REID MATCH] journey={journey_id} {source_camera}->{target_camera} "
                            f"track={candidate_id} cosine={score:.3f}"
                        )
                    if not pending_items:
                        pending_reid.pop((source_camera, target_camera), None)

                # Camera 1 is a trigger/registration camera and may not have a
                # topology tracker at all. Only topology cameras expose dropped_tracks.
                if camera_id in transition_trackers:
                    for dropped_track_id in transition_trackers[camera_id].detector.dropped_tracks:
                        runtime_reid.forget_track(camera_id, int(dropped_track_id))

                stale_keys = [
                    key for key, last_seen in track_last_seen.items()
                    if key[0] == camera_id and frame_id - last_seen > Config.TRANSITION_FORGET_FRAMES
                ]
                for stale_key in stale_keys:
                    stale_track_id = stale_key[1]
                    global_id = journey_by_track.get(stale_key)
                    if camera_id in GALLERY_CAMERAS and global_id is not None:
                        finish_gallery(camera_id, stale_track_id, global_id)
                    elif camera_id in FEATURE_CAMERAS:
                        feature_managers[camera_id].end_track(camera_id, stale_track_id)
                    journey_by_track.pop(stale_key, None)
                    track_last_seen.pop(stale_key, None)
                    registered_tracks.discard(stale_key)
                    plate_votes.pop(stale_key, None)
                    runtime_reid.forget_track(camera_id, stale_track_id)
                    camera2_feature_closed_tracks.discard(stale_key)
                    camera2_interior_seen.discard(stale_key)
                    movement_last_seen.pop(stale_key, None)
                    last_centers.pop(stale_key, None)
                    movement_scores.pop(stale_key, None)
                    movement_state.pop(stale_key, None)
                    if camera_id == 1:
                        sessions.release_camera1_track(stale_track_id)
                    if camera_id == 2:
                        completed = sessions.finish_on_camera2_track_lost(stale_track_id)
                        if completed:
                            registration_completed = True

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
                    key = (camera_id, track_id)
                    x1, y1, x2, y2 = map(int, box)
                    global_id = journey_by_track.get(key)
                    if camera_id == 1:
                        # Scan station: blue detections, green tracks inside scan zone.
                        color = (0, 255, 0) if track_id in active_ids else (255, 0, 0)
                        cv2.rectangle(display, (x1, y1), (x2, y2), color, 2)
                        if track_id in active_ids and global_id is not None:
                            plate, _ = best_plate(journey_plate_votes.get(global_id, {}))
                            if plate != "UNKNOWN":
                                draw_text_label(display, box, plate, color)
                    elif global_id is not None:
                        # Identified vehicles remain green regardless of motion.
                        color = (0, 255, 0)
                        cv2.rectangle(display, (x1, y1), (x2, y2), color, 2)
                        plate, _ = best_plate(journey_plate_votes.get(global_id, {}))
                        if plate != "UNKNOWN":
                            draw_text_label(display, box, plate, color)
                    elif movement_state.get(key, False):
                        # Moving but not yet identified: yellow with camera-local BoT-SORT ID.
                        color = (0, 255, 255)
                        cv2.rectangle(display, (x1, y1), (x2, y2), color, 2)
                        draw_text_label(display, box, f"LOCAL {track_id}", color)
                    else:
                        # Stationary vehicles: red, no label.
                        color = (0, 0, 255)
                        cv2.rectangle(display, (x1, y1), (x2, y2), color, 2)

                # Camera 1 builds the registration gallery but has no route topology lines.
                if camera_id != 1:
                    for line in network.camera(camera_id).lines:
                        p1, p2 = tuple(map(int, line.p1)), tuple(map(int, line.p2))
                        # Bright magenta transition lines stand out from vehicle boxes.
                        cv2.line(display, p1, p2, (255, 0, 255), 3)
                        cv2.circle(display, p1, 6, (255, 0, 255), -1)
                        cv2.circle(display, p2, 6, (255, 0, 255), -1)

                tile = cv2.resize(display, TILE_SIZE)
                cv2.rectangle(tile, (0, 0), (TILE_SIZE[0], 30), (20, 20, 20), -1)
                phase = (
                    "REGISTRATION + RE-ID GALLERY" if camera_id == 1
                    else "SCAN ZONE / RE-ID GALLERY" if camera_id in GALLERY_CAMERAS
                    else "MOVEMENT + TOPOLOGY + RE-ID"
                )
                cv2.putText(tile, f"CAM {camera_id} | {phase}", (10, 21),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2, cv2.LINE_AA)
                tiles[camera_id] = tile
                frame_ids[camera_id] += 1

            if not tiles:
                # Camera 1 deliberately skips inference on idle frames. That leaves
                # this iteration without display tiles, but must not stop the
                # controller while any stream is still open.
                if not captures:
                    break
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
                continue

            # Display only streams that are currently active; inactive cameras stay closed.
            ordered_ids = sorted(tiles)
            # Keep each camera tile at 16:9. Up to four cameras use the same
            # 2x2 layout as run_feature_capture; larger sets use 3 columns.
            columns = 2 if len(ordered_ids) <= 4 else 3
            cell_width = 1280 // columns
            cell_height = int(cell_width * 9 / 16)
            blank = np.zeros((cell_height, cell_width, 3), dtype=np.uint8)
            rows = []
            for offset in range(0, len(ordered_ids), columns):
                row_tiles = [
                    cv2.resize(tiles[cid], (cell_width, cell_height))
                    for cid in ordered_ids[offset:offset + columns]
                ]
                while len(row_tiles) < columns:
                    row_tiles.append(blank.copy())
                rows.append(cv2.hconcat(row_tiles))
            if rows:
                grid = cv2.vconcat(rows)
                # Match the actual grid dimensions instead of stretching it into
                # a fixed 1280x720 window (which distorted the camera images).
                cv2.resizeWindow(WINDOW_NAME, grid.shape[1], grid.shape[0])
                cv2.imshow(WINDOW_NAME, grid)
            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), 27):
                break
    finally:
        for cap in captures.values():
            cap.release()
        cv2.destroyAllWindows()
        for camera_id, manager in feature_managers.items():
            for (cam, track_id), gallery in manager.close_all().items():
                global_id = journey_by_track.get((cam, track_id))
                sample_count = len(gallery.get("original", [])) + len(gallery.get("flipped", []))
                if global_id is not None and cam in GALLERY_CAMERAS:
                    runtime_reid.add_identity_gallery(global_id, gallery)
                    if database is not None:
                        for mirrored, key_name in ((False, "original"), (True, "flipped")):
                            for vector in gallery.get(key_name, []):
                                database.save_embedding(global_id, cam, track_id, frame_ids.get(cam, 0), vector, mirrored)
                print(
                    f"[SHUTDOWN GALLERY] camera={cam} track={track_id} "
                    f"samples={sample_count} global_id={global_id if global_id is not None else '-'}"
                )
        plate_summary = {
            str(journey_id): {
                "plate": best_plate(votes)[0],
                "confidence": best_plate(votes)[1],
                "votes": {plate: len(scores) for plate, scores in votes.items()},
            }
            for journey_id, votes in journey_plate_votes.items()
        }
        report = {
            "elapsed_seconds": round(time.time() - started_at, 2),
            "video_sources": {str(cid): str(Config.CAMERA_VIDEO_PATHS.get(cid, "")) for cid in range(1, 10)},
            "frames_processed": {str(cid): int(count) for cid, count in frame_ids.items()},
            "streams_ended": sorted(int(cid) for cid in ended),
            "registered_journeys": len(session_by_journey),
            "reid_matches": reid_matches,
            "reid_expired_handoffs": reid_expired,
            "journey_plates": plate_summary,
            "feature_galleries_closed": {str(cid): int(count) for cid, count in feature_closed.items()},
            "ocr_cameras": list(OCR_CAMERAS),
            "database_writes": "enabled" if database is not None else "disabled",
        }
        REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[CONTROLLER] Run report written to {REPORT_PATH}")
        print("[CONTROLLER] Closed streams. Feature galleries closed:", dict(feature_closed))
        if database is not None:
            database.close()


if __name__ == "__main__":
    import traceback

    try:
        main()
    except BaseException:
        error_text = traceback.format_exc()
        error_path = ROOT / "startup_error.log"
        try:
            error_path.write_text(error_text, encoding="utf-8")
        except Exception:
            pass
        print("\n[CONTROLLER FATAL ERROR] Full traceback:")
        print(error_text)
        print(f"[CONTROLLER FATAL ERROR] Saved to: {error_path}")
        try:
            input("Press Enter to close...")
        except (EOFError, OSError):
            pass
        raise
