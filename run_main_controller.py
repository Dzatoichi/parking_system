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
        sample_every=max(1, int(getattr(Config, "RUNTIME_REID_EVERY_N_FRAMES", 2))),
        min_samples=max(1, int(getattr(Config, "RUNTIME_REID_MIN_SAMPLES", 1))),
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
    # Negative IDs are provisional, unrecognized journeys. They preserve the
    # vehicle's route across cameras without pretending we know its plate.
    next_unidentified_journey = -1
    # Independent FIFO queues for each directed camera-to-camera barrier.
    pending_reid: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    arrived_fifo: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    registered_tracks: set[tuple[int, int]] = set()
    plate_votes: dict[tuple[int, int], dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    journey_plate_votes: dict[int, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    feature_closed = Counter()
    registration_completed = False
    search_mode = False
    scan_pending: list[tuple[int, str, int, str]] = []
    # Journeys already assigned to camera-2 tracks remain part of the scan display
    # until their camera-2 topology EXIT line fires. Polygon membership is not an exit signal.
    scan_camera2_journeys: set[int] = set()
    last_centers: dict[tuple[int, int], tuple[float, float]] = {}
    movement_scores: dict[tuple[int, int], float] = {}
    movement_state: dict[tuple[int, int], bool] = {}
    movement_last_seen: dict[tuple[int, int], int] = {}
    track_last_seen: dict[tuple[int, int], int] = {}
    camera2_interior_seen: set[tuple[int, int]] = set()
    # First frame each camera-2 track enters a scan lane; FIFO order must not
    # depend on camera-local tracker IDs, which are arbitrary identifiers.
    scan_zone_first_seen: dict[tuple[int, int], int] = {}
    camera2_feature_closed_tracks: set[tuple[int, int]] = set()
    # Camera 1 remains the persistent scan/trigger view; the second tile follows
    # the current downstream search destination. Cached tiles survive idle skips.
    display_camera_id = 1
    # Dynamic display pool: camera 1 is persistent, scan cameras are temporary,
    # and the current route-search destination is added while its task is active.
    visual_camera_pool: set[int] = {1}
    last_tiles: dict[int, np.ndarray] = {}

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

    def start_registration(track_id: int, frame_id: int, current_tracks) -> None:
        key = (1, int(track_id))
        if key in registered_tracks:
            return
        entry_bbox = next((box for tid, box in current_tracks if int(tid) == int(track_id)), None)
        entry_lane = feature_managers[1]._matching_profile(1, entry_bbox) if entry_bbox is not None else None
        if entry_lane is None:
            print(f"[SCAN FIFO WARNING] camera=1 track={track_id} has no LEFT/RIGHT entry lane; not enqueueing")
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
        visual_camera_pool.update(SCAN_CAMERAS)
        # Store the actual target-camera frame after timestamp seeking, otherwise
        # the FIFO TTL would be measured from frame zero and could expire instantly.
        scan_pending.append((journey_number, session.session_id, frame_ids.get(2, 0), entry_lane))
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
            if journey_number is not None and journey_number > 0 and camera_id in GALLERY_CAMERAS:
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
            # If the focused route stream ended, return the display to the trigger
            # (or the next available stream) while continuing the controller loop.
            if display_camera_id not in captures:
                display_camera_id = 1 if 1 in captures else min(captures)
                print(f"[DISPLAY FOCUS] camera={display_camera_id} reason=focused_stream_unavailable")
            scan_zone_active_cameras: set[int] = set()
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
                    # Display-state tracking must use actual polygon membership,
                    # not active gallery IDs: galleries intentionally remain active
                    # after a vehicle leaves the zone so sampling can continue.
                    if camera_id in SCAN_CAMERAS and any(
                        feature_managers[camera_id].is_in_zone(camera_id, bbox)
                        for _tid, bbox in tracks
                    ):
                        scan_zone_active_cameras.add(camera_id)
                    if camera_id == 2:
                        # FIFO is permitted only between the scan station and the
                        # useful overview camera. It is never used on cameras 4-9.
                        fifo_ttl = max(1, int(getattr(Config, "SCAN_FIFO_TTL_FRAMES", 900)))
                        fresh_scan_queue = []
                        for pending_global_id, pending_session_id, created_camera2_frame, pending_lane in scan_pending:
                            if frame_id - created_camera2_frame > fifo_ttl:
                                print(f"[SCAN FIFO EXPIRED] global_id={pending_global_id} waited_frames={frame_id - created_camera2_frame}")
                                if database is not None:
                                    database.record_event(
                                        2, -1, frame_id, "scan_fifo_expired",
                                        global_id=pending_global_id, source_camera_id=1, target_camera_id=2,
                                        details={"target_frames_waited": int(frame_id - created_camera2_frame)},
                                    )
                            else:
                                fresh_scan_queue.append((pending_global_id, pending_session_id, created_camera2_frame, pending_lane))
                        scan_pending[:] = fresh_scan_queue
                        # Bind only on the frame a track is actually inside camera 2's
                        # configured scan polygon. Active galleries persist outside the zone,
                        # so active_ids alone must never drive FIFO assignment.
                        in_zone_tracks = []
                        for scan_track_id, scan_bbox in tracks:
                            lane = feature_managers[2]._matching_profile(2, scan_bbox)
                            if lane is not None:
                                scan_key = (2, int(scan_track_id))
                                scan_zone_first_seen.setdefault(scan_key, int(frame_id))
                                in_zone_tracks.append((int(scan_track_id), lane))
                        # Actual first zone-entry time, not local track ID, defines FIFO.
                        for scan_track_id, lane in sorted(
                            in_zone_tracks,
                            key=lambda item: (scan_zone_first_seen.get((2, item[0]), frame_id), item[0]),
                        ):
                            key = (2, int(scan_track_id))
                            if key in journey_by_track:
                                continue
                            queue_index = next(
                                (i for i, item in enumerate(scan_pending) if item[3] == lane),
                                None,
                            )
                            if queue_index is None:
                                continue
                            global_id, session_id, _created_camera2_frame, _pending_lane = scan_pending.pop(queue_index)
                            journey_by_track[key] = global_id
                            scan_camera2_journeys.add(int(global_id))
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
                                start_registration(int(tid), frame_id, tracks)
                    if camera_id in OCR_CAMERAS and frame_id % max(1, Config.OCR_EVERY_N_FRAMES) == 0 and active_ids:
                        # Plate OCR is performed only at the entry camera. Camera 2
                        # receives the already-read plate through lane-specific FIFO.
                        scan_zone_tracks = [
                            (int(tid), box) for tid, box in zip(ids, boxes)
                            if int(tid) in active_ids
                            and feature_managers[camera_id].is_in_zone(camera_id, box)
                        ]
                        for tid, reading in plate_ocr.recognize(frame, scan_zone_tracks).items():
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
                # Diagnostic Re-ID: compare each newly accepted single-vector observation
                # against every registered vehicle gallery and print the best cosine score.
                # FIFO still controls identity handoff; these scores are informational only.
                if camera_id != 1 and sampled_embeddings:
                    identity_labels = {
                        int(journey_id): best_plate(votes)[0]
                        for journey_id, votes in journey_plate_votes.items()
                    }
                    for sampled_track_id, vector in sampled_embeddings:
                        runtime_reid.log_feature_against_all_identities(
                            camera_id, int(sampled_track_id), vector, identity_labels
                        )

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
                            # Do not strand a visible vehicle just because Re-ID/OCR
                            # has not identified it yet. Keep searching downstream.
                            journey_number = next_unidentified_journey
                            next_unidentified_journey -= 1
                            print(
                                f"[UNIDENTIFIED HANDOFF] camera={command.source_camera} "
                                f"local_id={command.track_id} provisional_journey={journey_number} "
                                f"next_camera={command.camera_id}"
                            )
                        if command.source_camera == 2 and journey_number > 0:
                            # Keep cameras 2/3 displayed until every registered vehicle
                            # has crossed camera 2's configured EXIT topology line.
                            scan_camera2_journeys.discard(int(journey_number))
                        if journey_number is None:
                            continue
                        session_id = session_for_journey(journey_number)
                        pair = (command.source_camera, command.camera_id)
                        # A topology EXIT creates a search task: lazily open only its
                        # destination camera, aligned to the source video's timestamp.
                        target_time = camera_times.get(command.source_camera, 0.0)
                        open_camera(command.camera_id, target_time)
                        if command.camera_id in captures:
                            display_camera_id = command.camera_id
                            visual_camera_pool.add(command.camera_id)
                            print(
                                f"[DISPLAY FOCUS] camera={display_camera_id} "
                                f"reason=search_handoff from={command.source_camera} "
                                f"journey={journey_number}"
                            )
                        finish_gallery(command.source_camera, command.track_id, journey_number)
                        # Camera 1 has no topology transitions. Every actual network handoff
                        # (cameras 2-9) must pass topology eligibility AND Re-ID.
                        if journey_number > 0 and command.source_camera not in GALLERY_CAMERAS:
                            runtime_reid.extend_identity(
                                journey_number, command.source_camera, command.track_id
                            )
                        pending_reid[pair].append(
                            (journey_number, frame_ids.get(command.camera_id, 0))
                        )
                        if database is not None and journey_number > 0:
                            database.record_event(
                                command.source_camera, command.track_id, command.frame_id,
                                "topology_exit", global_id=journey_number,
                                source_camera_id=command.source_camera, target_camera_id=command.camera_id,
                                movement_state="moving",
                            )
                        # Source track embeddings are no longer needed once handed off.
                        runtime_reid.forget_track(command.source_camera, command.track_id)

                        # Registration is considered complete exactly at camera-2 EXIT.
                        if command.source_camera == 2 and journey_number > 0:
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
                        pair = (int(command.source_camera), int(command.camera_id))
                        arrived_fifo[pair].append((int(command.track_id), int(command.frame_id)))
                        print(
                            f"[BARRIER FIFO ARRIVAL] {pair[0]}->{pair[1]} "
                            f"track={command.track_id} position={len(arrived_fifo[pair])}"
                        )

                # Resolve each directed barrier independently using arrival order.
                # Re-ID similarity cannot block propagation of a registered vehicle's plate.
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
                    arrival_items = arrived_fifo[(source_camera, target_camera)]
                    arrival_items[:] = [
                        item for item in arrival_items
                        if frame_id - item[1] <= ttl
                        and (target_camera, item[0]) not in journey_by_track
                    ]
                    while pending_items and arrival_items:
                        journey_id, _created_target_frame = pending_items.pop(0)
                        candidate_id, arrival_frame = arrival_items.pop(0)
                        key = (target_camera, candidate_id)
                        if key in journey_by_track:
                            continue
                        journey_by_track[key] = int(journey_id)
                        if database is not None and journey_id > 0 and target_camera not in GALLERY_CAMERAS:
                            for vector in runtime_reid.track_features.get(key, []):
                                database.save_embedding(journey_id, target_camera, candidate_id, frame_id, vector)
                        session_id = session_by_journey.get(journey_id)
                        if session_id:
                            current = sessions.get_session(session_id)
                            if current and current["status"] == "active":
                                try:
                                    sessions.bind_track(session_id, target_camera, candidate_id)
                                except (KeyError, ValueError) as exc:
                                    print(f"[SESSION BIND WARNING] {exc}")
                        if database is not None and journey_id > 0:
                            database.record_event(
                                target_camera, candidate_id, frame_id, "fifo_handoff",
                                global_id=journey_id, source_camera_id=source_camera,
                                target_camera_id=target_camera,
                                movement_state="moving" if movement_state.get(key, False) else "stationary",
                                details={"arrival_frame": int(arrival_frame), "match_method": "fifo"},
                            )
                        if journey_id > 0:
                            reid_matches.append({
                                "journey_id": int(journey_id),
                            "source_camera": int(source_camera),
                            "target_camera": int(target_camera),
                            "target_track_id": int(candidate_id),
                            "cosine_similarity": None,
                                "match_method": "fifo",
                            })
                        print(
                            f"[BARRIER FIFO MATCH] journey={journey_id} "
                            f"{source_camera}->{target_camera} track={candidate_id} "
                            f"arrival_frame={arrival_frame}"
                            + (" status=identified" if journey_id > 0 else " status=unidentified_continuing")
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
                    scan_zone_first_seen.pop(stale_key, None)
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
                # Collect rendered tiles first. Display selection is made after all
                # cameras have been processed so scan-zone state is complete.
                tiles[camera_id] = tile
                last_tiles[camera_id] = tile
                frame_ids[camera_id] += 1

            # When the final downstream journey/search task disappears, return
            # the display to camera 1. The trigger stream has remained active
            # throughout; this changes focus only, not the processing state.
            downstream_tracks_active = any(camera_id != 1 for camera_id, _ in journey_by_track)
            search_tasks_pending = bool(scan_pending or any(pending_reid.values()))
            scan_collection_active = bool(scan_pending or scan_camera2_journeys)
            if (
                display_camera_id != 1
                and 1 in captures
                and not downstream_tracks_active
                and not search_tasks_pending
                and not scan_collection_active
            ):
                display_camera_id = 1
                print("[DISPLAY FOCUS] camera=1 reason=search_tasks_finished")

            # Camera 1 is permanent. Keep cameras 2/3 visible while any registered
            # journey is waiting for camera 2 or has a bound camera-2 track that has
            # not crossed its topology EXIT line. Do not infer completion from zone
            # polygon membership or gallery activity; multiple cars may overlap in time.
            scan_view_active = bool(scan_pending or scan_camera2_journeys)
            if scan_view_active:
                visual_camera_pool.update(SCAN_CAMERAS)
            else:
                visual_camera_pool.difference_update(cid for cid in SCAN_CAMERAS if cid != 1)
            if display_camera_id != 1 and display_camera_id in captures:
                visual_camera_pool.add(display_camera_id)
            else:
                # Remove an obsolete route tile when no route search is focused.
                visual_camera_pool.difference_update(
                    cid for cid in list(visual_camera_pool)
                    if cid != 1 and cid not in SCAN_CAMERAS
                )

            available_tiles = {
                cid: tile for cid, tile in last_tiles.items()
                if cid in captures and cid in visual_camera_pool
            }
            shown_ids = sorted(available_tiles)

            if not shown_ids:
                # Camera 1 deliberately skips inference on idle frames. Cached tiles
                # normally keep the UI alive; this guard prevents accidental shutdown.
                if not captures:
                    break
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
                continue

            # Render every camera currently in the pool in a compact 2-column grid.
            # Missing tiles are not added to the pool; only currently available frames show.
            columns = 2 if len(shown_ids) > 1 else 1
            rows = (len(shown_ids) + columns - 1) // columns
            blank = np.zeros((TILE_SIZE[1], TILE_SIZE[0], 3), dtype=np.uint8)
            cells = [available_tiles[cid] for cid in shown_ids]
            while len(cells) < rows * columns:
                cells.append(blank)
            grid_rows = [
                np.hstack(cells[row * columns:(row + 1) * columns])
                for row in range(rows)
            ]
            grid = grid_rows[0] if len(grid_rows) == 1 else np.vstack(grid_rows)
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
