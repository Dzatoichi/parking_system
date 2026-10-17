"""Nine-camera controller with lane-constrained scan FIFO and topology handoffs.

Camera 1 registers vehicles and reads plates. Camera 1 -> 2 uses FIFO constrained by
LEFT/RIGHT scan lanes and first zone-entry time. Camera 3 currently uses FIFO for
topology handoffs; other downstream camera pairs use topology-gated ReID. OCR runs on
camera 1 only.
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
        
        while captures:
            # If the focused route stream ended, return the display to the trigger
            # (or the next available stream) while continuing the controller loop.
            if display_camera_id not in captures:
                display_camera_id = 1 if 1 in captures else min(captures)
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
                                                continue

                    if command.type is CommandType.SEARCH_ON_CAMERA:
                        source_key = (command.source_camera, int(command.track_id))
                        journey_number = journey_by_track.pop(source_key, None)
                        if journey_number is None:
                            # Do not strand a visible vehicle just because Re-ID/OCR
                            # has not identified it yet. Keep searching downstream.
                            journey_number = next_unidentified_journey
                            next_unidentified_journey -= 1
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
                                                    if command.source_camera == 2:
                            # Mark closure only for the track that emitted this EXIT event.
                            camera2_feature_closed_tracks.add(source_key)
                            camera2_interior_seen.discard(source_key)
                        finish_gallery(command.source_camera, command.track_id, journey_number)
                        # Camera 1 has no topology transitions. Topology EXIT advances the search;
                        # Re-ID is diagnostic and must never block the next-camera handoff.
                        if command.source_camera not in GALLERY_CAMERAS:
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
                        label_plate, _ = best_plate(journey_plate_votes.get(int(journey_number), {}))
                        transition_label = (
                            label_plate if label_plate != "UNKNOWN"
                            else f"LOCAL {int(command.track_id)}"
                        )
                        print(
                            f"[TRANSITION] {command.source_camera}->{command.camera_id} "
                            f"{transition_label}"
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
                        arrived_candidates[pair].append((int(command.track_id), int(command.frame_id)))
                        
                # Scores shown over boxes must correspond to all journeys actively
                # waiting for this camera, not the best match against the entire gallery.
                for score_key in [item for item in reid_candidate_scores if item[0] == camera_id]:
                    reid_candidate_scores.pop(score_key, None)

                # Resolve each directed barrier independently using topology-gated ReID scores.
                # Low-confidence or ambiguous matches stay unresolved; never fall back to FIFO.
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
                            if database is not None and journey_id > 0:
                                database.record_event(
                                    target_camera, -1, frame_id, "reid_handoff_expired",
                                    global_id=journey_id, source_camera_id=source_camera,
                                    target_camera_id=target_camera,
                                    details={"target_frames_waited": int(frame_id - created_target_frame)},
                                )
                                                    else:
                            active_items.append((journey_id, created_target_frame))
                    pending_items[:] = active_items
                    if not pending_items:
                        pending_reid.pop((source_camera, target_camera), None)
                        continue
                    arrival_items = arrived_candidates[(source_camera, target_camera)]
                    arrival_items[:] = [
                        item for item in arrival_items
                        if frame_id - item[1] <= ttl
                        and (target_camera, item[0]) not in journey_by_track
                    ]
                    # Camera 3 remains FIFO for now, as requested. Topology ENTER
                    # events define the eligible target tracks; queue order decides identity.
                    if target_camera == 3:
                        max_early_frames = max(0, int(getattr(Config, "REID_MATCH_MAX_EARLY_FRAMES", 0)))
                        arrival_items.sort(key=lambda item: (item[1], item[0]))
                        while pending_items and arrival_items:
                            journey_id, created_target_frame = pending_items[0]
                            eligible_index = next((
                                i for i, (_candidate_id, arrival_frame) in enumerate(arrival_items)
                                if arrival_frame >= created_target_frame - max_early_frames
                            ), None)
                            if eligible_index is None:
                                break
                            candidate_id, arrival_frame = arrival_items.pop(eligible_index)
                            pending_items.pop(0)
                            key = (target_camera, int(candidate_id))
                            if key in journey_by_track:
                                continue
                            journey_by_track[key] = journey_id
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
                                    details={
                                        "arrival_frame": arrival_frame,
                                        "match_method": "topology+fifo",
                                    },
                                )
                            match_plate, _ = best_plate(journey_plate_votes.get(int(journey_id), {}))
                            match_label = match_plate if match_plate != "UNKNOWN" else f"LOCAL {candidate_id}"
                            print(f"[MATCH] {source_camera}->{target_camera} {match_label}")
                        if not pending_items:
                            pending_reid.pop((source_camera, target_camera), None)
                        continue
                    # Candidate generation is spatial/topological: a candidate must
                    # have crossed the ENTER line from this exact source camera and be
                    # inside the TTL window. Identity is decided by Re-ID, never queue order.
                    min_margin = float(getattr(Config, "REID_MATCH_MIN_MARGIN", 0.04))
                    max_early_frames = max(0, int(getattr(Config, "REID_MATCH_MAX_EARLY_FRAMES", 0)))
                    scored_pairs = []
                    for pending_index, (journey_id, created_target_frame) in enumerate(pending_items):
                        if journey_id == 0 or not runtime_reid.identity_gallery.get(int(journey_id)):
                            continue
                        for arrival_index, (candidate_id, arrival_frame) in enumerate(arrival_items):
                            # Do not steal a track that crossed the target ENTER line
                            # long before this source EXIT created the search task.
                            if arrival_frame < created_target_frame - max_early_frames:
                                continue
                            key = (target_camera, int(candidate_id))
                            if key in journey_by_track:
                                continue
                            # Keep the diagnostic log, but rank every viable pair by its
                            # raw appearance score, including scores below the acceptance
                            # threshold, so the runner-up is not silently ignored.
                            runtime_reid.match_track_to_journey(
                                target_camera, int(candidate_id), int(journey_id)
                            )
                            track_features = runtime_reid.track_features.get(key, [])
                            identity_features = runtime_reid.identity_gallery.get(int(journey_id), [])
                            if len(track_features) < runtime_reid.min_samples or not identity_features:
                                continue
                            raw_score, _mean_topk = RuntimeReID._similarity_scores(
                                track_features[-1:], identity_features
                            )
                            if raw_score >= 0.0:
                                scored_pairs.append((
                                    float(raw_score), int(journey_id), int(candidate_id),
                                    int(arrival_frame), pending_index, arrival_index
                                ))
                                plate, _ = best_plate(journey_plate_votes.get(int(journey_id), {}))
                                reid_candidate_scores[(target_camera, int(candidate_id))].append(
                                    (float(raw_score), int(journey_id), plate)
                                )

                    scored_pairs.sort(key=lambda item: item[0], reverse=True)
                    if scored_pairs:
                        best = scored_pairs[0]
                        # Require both the configured similarity threshold and a margin
                        # over every competing journey/track pairing.
                        second_score = scored_pairs[1][0] if len(scored_pairs) > 1 else -1.0
                        if best[0] >= runtime_reid.threshold and best[0] - second_score >= min_margin:
                            score, journey_id, candidate_id, arrival_frame, pending_index, arrival_index = best
                            key = (target_camera, candidate_id)
                            if key not in journey_by_track:
                                pending_items.pop(pending_index)
                                arrival_items.pop(arrival_index)
                                journey_by_track[key] = journey_id
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
                                        target_camera, candidate_id, frame_id, "reid_handoff",
                                        global_id=journey_id, source_camera_id=source_camera,
                                        target_camera_id=target_camera,
                                        movement_state="moving" if movement_state.get(key, False) else "stationary",
                                        details={
                                            "arrival_frame": arrival_frame,
                                            "match_method": "topology+reid",
                                            "cosine_similarity": round(score, 4),
                                            "score_margin": round(best[0] - second_score, 4),
                                        },
                                    )
                                reid_matches.append({
                                    "journey_id": journey_id,
                                    "source_camera": source_camera,
                                    "target_camera": target_camera,
                                    "target_track_id": candidate_id,
                                    "cosine_similarity": round(score, 4),
                                    "score_margin": round(best[0] - second_score, 4),
                                    "match_method": "topology+reid",
                                })
                                match_plate, _ = best_plate(journey_plate_votes.get(int(journey_id), {}))
                                match_label = match_plate if match_plate != "UNKNOWN" else f"LOCAL {candidate_id}"
                                print(f"[MATCH] {source_camera}->{target_camera} {match_label}")
                        else:
                            reason = (
                                "below_similarity_threshold"
                                if best[0] < runtime_reid.threshold
                                else "ambiguous_score_margin"
                            )
                                                elif pending_items and arrival_items:
                                            if not pending_items:
                        pending_reid.pop((source_camera, target_camera), None)

                # Camera 1 is a trigger/registration camera and may not have a
                # topology tracker at all. Only topology cameras expose dropped_tracks.
                if camera_id in transition_trackers:
                    for dropped_track_id in transition_trackers[camera_id].detector.dropped_tracks:
                        dropped_key = (camera_id, int(dropped_track_id))
                        # A detector timeout is not proof of a camera transition. Keep
                        # samples for an assigned journey until its EXIT event arrives.
                        has_open_gallery = (
                            camera_id in FEATURE_CAMERAS
                            and dropped_key in getattr(feature_managers[camera_id], "_galleries", {})
                        )
                        if camera_id != 1 and (dropped_key in journey_by_track or has_open_gallery):
                            continue
                        runtime_reid.forget_track(camera_id, int(dropped_track_id))

                stale_keys = [
                    key for key, last_seen in track_last_seen.items()
                    if key[0] == camera_id and frame_id - last_seen > Config.TRANSITION_FORGET_FRAMES
                ]
                for stale_key in stale_keys:
                    stale_track_id = stale_key[1]
                    global_id = journey_by_track.get(stale_key)
                    has_open_gallery = (
                        camera_id in FEATURE_CAMERAS
                        and stale_key in getattr(feature_managers[camera_id], "_galleries", {})
                    )
                    if camera_id != 1 and (global_id is not None or has_open_gallery):
                        # Losing a local detection is NOT a topology transition.
                        # Preserve the journey/gallery state until this exact track
                        # crosses its configured EXIT line or the run ends.
                        track_last_seen.pop(stale_key, None)
                                                continue
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
                    # Only show scores against journeys actively waiting for this camera.
                    # Scan-zone overlays intentionally omit Re-ID diagnostics.
                    in_scan_zone = (
                        camera_id in FEATURE_CAMERAS
                        and feature_managers[camera_id].is_in_zone(camera_id, box)
                    )
                    candidate_scores = sorted(
                        reid_candidate_scores.get(key, []),
                        key=lambda item: item[0],
                        reverse=True,
                    )
                    if candidate_scores:
                        visible_scores = []
                        for score, candidate_journey, candidate_plate in candidate_scores[:3]:
                            candidate_name = (
                                candidate_plate if candidate_plate and candidate_plate != "UNKNOWN"
                                else f"J{candidate_journey}"
                            )
                            visible_scores.append(f"{candidate_name}:{score:.2f}")
                        extra = len(candidate_scores) - len(visible_scores)
                        if extra > 0:
                            visible_scores.append(f"+{extra}")
                        reid_label = "REID " + " ".join(visible_scores)
                    else:
                        reid_label = "REID --"

                    if camera_id == 1:
                        color = (0, 255, 0) if track_id in active_ids else (255, 0, 0)
                    elif global_id is not None and global_id > 0:
                        color = (0, 255, 0)
                    elif movement_state.get(key, False) or (global_id is not None and global_id < 0):
                        color = (0, 255, 255)
                    else:
                        color = (0, 0, 255)
                    cv2.rectangle(display, (x1, y1), (x2, y2), color, 2)

                    label_parts = [f"LOCAL {track_id}"]
                    if not in_scan_zone:
                        label_parts.append(reid_label)
                    if global_id is not None and global_id < 0:
                        label_parts.append("SEARCHING")
                    elif global_id is not None and global_id > 0:
                        plate, _ = best_plate(journey_plate_votes.get(global_id, {}))
                        if plate != "UNKNOWN":
                            label_parts.append(plate)
                    draw_text_label(display, box, " | ".join(label_parts), color)

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
                    if database is not None and global_id > 0:
                        for mirrored, key_name in ((False, "original"), (True, "flipped")):
                            for vector in gallery.get(key_name, []):
                                database.save_embedding(global_id, cam, track_id, frame_ids.get(cam, 0), vector, mirrored)
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
