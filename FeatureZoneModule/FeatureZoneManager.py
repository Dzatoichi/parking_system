"""Zone-based Re-ID feature sampling with camera-specific anchor points."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping
import cv2
import numpy as np
import yaml

from Config import Config

@dataclass
class TrackGallery:
    """Embeddings for one local track observation."""
    camera_id: int
    track_id: int
    zone_profile: str
    original: list[np.ndarray] = field(default_factory=list)
    flipped: list[np.ndarray] = field(default_factory=list)
    last_sample_frame: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"camera_id": self.camera_id, "track_id": self.track_id,
                "zone_profile": self.zone_profile, "original": list(self.original),
                "flipped": list(self.flipped), "sample_count": len(self.original)}

class FeatureZoneManager:
    """Capture only on cameras 1-3: cam1 bottom-center, cam2 right-center, cam3 top-center.
    Cameras 4-9 are intentionally ignored by this module.
    """
    def __init__(self, features_manager, config_path: str | Path = "feature_zones.yaml",
                 similarity_threshold: float | None = None,
                 sample_every_n_frames: int | None = None, min_crop_size: int | None = None):
        self.features_manager = features_manager
        with open(config_path, "r", encoding="utf-8") as stream:
            self.config = yaml.safe_load(stream) or {}
        # Thresholds and sampling intervals are centralized in Config.py.
        # feature_zones.yaml contains camera geometry only.
        threshold = Config.GALLERY_DUPLICATE_SIM_THRESHOLD if similarity_threshold is None else similarity_threshold
        interval = Config.GALLERY_SAMPLE_EVERY_N_FRAMES if sample_every_n_frames is None else sample_every_n_frames
        crop_size = Config.FEATURE_MIN_CROP_SIZE if min_crop_size is None else min_crop_size
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("similarity_threshold must be between 0 and 1")
        if interval < 1:
            raise ValueError("sample_every_n_frames must be >= 1")
        if crop_size < 1:
            raise ValueError("min_crop_size must be >= 1")
        self.similarity_threshold, self.sample_every_n_frames, self.min_crop_size = float(threshold), int(interval), int(crop_size)
        self._galleries: dict[tuple[int, int], TrackGallery] = {}
        # Tracks explicitly closed (e.g. camera-2 frame exit) cannot reactivate
        # while the tracker still reports them. They become eligible again only
        # after disappearing from the visible track set.
        self._closed_tracks: set[tuple[int, int]] = set()
        # Latest comparison against the last accepted ORIGINAL embedding, per local track.
        # Kept between sampling frames so the UI can display it beneath the bbox.
        self.last_comparison_by_track: dict[int, dict[str, float]] = {}
        self._rectangles = self._parse_rectangles(self.config.get("cameras", {}))

    @staticmethod
    def _parse_rectangles(cameras: Mapping) -> dict[int, dict[str, tuple[int, int, int, int]]]:
        """Parse rectangular zones from two opposite corners, p1 and p2."""
        parsed: dict[int, dict[str, tuple[int, int, int, int]]] = {}
        for camera_key, camera_cfg in cameras.items():
            try:
                camera_id = int(camera_key)
            except (TypeError, ValueError):
                continue
            profiles = {}
            for profile_name, raw in (camera_cfg or {}).items():
                if not raw:
                    continue
                if not isinstance(raw, Mapping) or "p1" not in raw or "p2" not in raw:
                    raise ValueError(f"Camera {camera_id} profile {profile_name!r} must define p1 and p2 rectangle corners")
                p1, p2 = raw["p1"], raw["p2"]
                if (not isinstance(p1, (list, tuple)) or len(p1) != 2 or not isinstance(p2, (list, tuple)) or len(p2) != 2):
                    raise ValueError(f"Camera {camera_id} profile {profile_name!r}: p1/p2 must be [x, y]")
                x1, y1 = int(p1[0]), int(p1[1])
                x2, y2 = int(p2[0]), int(p2[1])
                left, right = sorted((x1, x2))
                top, bottom = sorted((y1, y2))
                if left == right or top == bottom:
                    raise ValueError(f"Camera {camera_id} profile {profile_name!r}: rectangle must have non-zero width and height")
                profiles[str(profile_name).upper()] = (left, top, right, bottom)
            parsed[camera_id] = profiles
        return parsed
    @staticmethod
    def anchor(camera_id: int, bbox) -> tuple[float, float]:
        camera_id = int(camera_id)
        if camera_id not in (1, 2, 3):
            raise ValueError("Feature capture anchors are defined only for cameras 1, 2, and 3")
        x1, y1, x2, y2 = map(float, bbox)
        if camera_id == 2:
            return x2, (y1 + y2) / 2.0
        if int(camera_id) == 3:
            return (x1 + x2) / 2.0, y1
        return (x1 + x2) / 2.0, y2

    def _matching_profile(self, camera_id: int, bbox) -> str | None:
        profiles = self._rectangles.get(int(camera_id), {})
        candidates = ("LEFT", "RIGHT") if int(camera_id) in (1, 2) else ("DEFAULT",)
        point = self.anchor(camera_id, bbox)
        # Deterministic priority if rectangles overlap; LEFT wins over RIGHT.
        x, y = point
        for name in candidates:
            if name in profiles:
                left, top, right, bottom = profiles[name]
                if left <= x <= right and top <= y <= bottom:
                    return name
        return None

    def is_in_zone(self, camera_id: int, bbox) -> bool:
        """Check scan-zone membership without extracting or storing appearance features."""
        if int(camera_id) not in (1, 2, 3):
            return False
        return self._matching_profile(int(camera_id), bbox) is not None

    def process_frame(self, camera_id: int, frame_id: int, frame: np.ndarray,
                      tracks: Iterable[tuple[int, Iterable[float]]],
                      entry_gate: str | None = None) -> dict[int, bool]:
        """Activate tracks when their anchor enters a zone, then sample them outside it too.

        Zone membership is an activation trigger, not a spatial restriction on every
        feature sample. All currently visible activated tracks on this camera are
        considered on sampling frames, so multiple vehicles can be processed in one
        batch. A new local track ID entering a zone gets its own gallery.
        """
        camera_id = int(camera_id)
        if camera_id not in (1, 2, 3):
            return {}

        # Trigger evaluation happens on every call, even when this frame is not a
        # feature-sampling frame, so frame skipping cannot silently miss activation.
        visible: dict[int, tuple[float, float, float, float]] = {}
        for track_id, bbox in tracks:
            visible[int(track_id)] = tuple(map(float, bbox))

        # A closed track may only be re-armed after it is no longer visible;
        # this prevents a boundary-touching track from opening a fresh gallery
        # on every subsequent frame.
        self._closed_tracks = {
            key for key in self._closed_tracks
            if key[0] != camera_id or key[1] in visible
        }
        for track_id, box in visible.items():
            key = (camera_id, track_id)
            if key not in self._galleries and key not in self._closed_tracks:
                profile = self._matching_profile(camera_id, box)
                if profile is not None:
                    self._galleries[key] = TrackGallery(camera_id, track_id, profile)

        if frame_id % self.sample_every_n_frames != 0:
            return {}

        h, w = frame.shape[:2]
        pending: list[tuple[int, str, np.ndarray]] = []
        for (gallery_camera, track_id), gallery in list(self._galleries.items()):
            if gallery_camera != camera_id or track_id not in visible:
                continue
            if gallery.last_sample_frame == frame_id:
                continue
            x1, y1, x2, y2 = map(int, visible[track_id])
            x1, x2 = max(0, x1), min(w, x2)
            y1, y2 = max(0, y1), min(h, y2)
            if x2 - x1 < self.min_crop_size or y2 - y1 < self.min_crop_size:
                continue
            crop = frame[y1:y2, x1:x2].copy()
            if crop.size:
                pending.append((track_id, gallery.zone_profile, crop))

        if not pending:
            return {}

        # Originals and horizontal flips are passed in a single extractor call.
        batch = []
        for _, _, crop in pending:
            batch.extend((crop, cv2.flip(crop, 1)))
        features = self.features_manager.extract_features(batch)
        if len(features) != len(batch):
            raise RuntimeError(f"Feature extractor returned {len(features)} vectors for {len(batch)} crops")

        decisions = {}
        for index, (track_id, profile, _) in enumerate(pending):
            original = self._normalize(features[2 * index])
            flipped = self._normalize(features[2 * index + 1])
            gallery = self._galleries[(camera_id, track_id)]
            gallery.last_sample_frame = int(frame_id)
            if gallery.original:
                # Temporal diversity sampling: compare only to the LAST ACCEPTED
                # original embedding. If this view is redundant, do not advance the
                # reference; the next sampled frame must still compare to the last
                # embedding that actually entered the gallery.
                similarity = float(
                    self.features_manager.calculate_similarity(original, gallery.original[-1])
                )
                cosine_distance = 1.0 - similarity
                self.last_comparison_by_track[track_id] = {
                    "cosine_similarity": similarity,
                    "cosine_distance": cosine_distance,
                }
                if similarity >= self.similarity_threshold:
                    decisions[track_id] = False
                    continue
            else:
                # No prior accepted original exists yet, so there is no pair to compare.
                self.last_comparison_by_track.pop(track_id, None)
            gallery.original.append(original)
            gallery.flipped.append(flipped)
            decisions[track_id] = True
        return decisions

    @staticmethod
    def _normalize(feature) -> np.ndarray:
        vector = np.asarray(feature, dtype=np.float32).reshape(-1)
        norm = float(np.linalg.norm(vector))
        if not np.isfinite(norm) or norm <= 1e-12:
            raise ValueError("Feature extractor returned a zero or non-finite embedding")
        return vector / norm

    def end_track(self, camera_id: int, track_id: int) -> dict[str, Any] | None:
        camera_id, track_id = int(camera_id), int(track_id)
        key = (camera_id, track_id)
        gallery = self._galleries.pop(key, None)
        if gallery is not None:
            self._closed_tracks.add(key)
        # Track IDs can be reused after a gallery closes; don't show stale
        # similarity metrics for a future track with the same local ID.
        if not any(existing_track_id == track_id for _, existing_track_id in self._galleries):
            self.last_comparison_by_track.pop(track_id, None)
        return gallery.as_dict() if gallery is not None else None

    def end_tracks_on_exit(self, camera_id: int, transition_events: Iterable[Any]) -> dict[int, dict[str, Any]]:
        completed = {}
        for event in transition_events:
            event_camera = getattr(event, "camera_id", None)
            role = getattr(getattr(event, "role", None), "value", getattr(event, "role", None))
            track_id = getattr(event, "track_id", None)
            if event_camera != int(camera_id) or str(role).upper() != "EXIT" or track_id is None:
                continue
            gallery = self.end_track(camera_id, int(track_id))
            if gallery is not None:
                completed[int(track_id)] = gallery
        return completed

    def active_track_keys(self) -> tuple[tuple[int, int], ...]:
        return tuple(self._galleries.keys())

    def close_all(self) -> dict[tuple[int, int], dict[str, Any]]:
        completed = {key: gallery.as_dict() for key, gallery in self._galleries.items()}
        self._galleries.clear()
        return completed
