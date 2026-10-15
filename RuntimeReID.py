"""In-memory Re-ID identity galleries and topology-scoped handoff matching."""
from __future__ import annotations

from collections import defaultdict
import logging

import numpy as np

from Config import Config

logger = logging.getLogger(__name__)


class RuntimeReID:
    """Keep per-journey appearance galleries and match only topology-eligible tracks."""

    def __init__(self, feature_manager, threshold=None, sample_every=5, min_samples=2):
        self.feature_manager = feature_manager
        self.threshold = float(
            Config.REID_SIMILARITY_THRESHOLD if threshold is None else threshold
        )
        self.sample_every = max(1, int(sample_every))
        self.min_samples = max(1, int(min_samples))
        self.identity_gallery: dict[int, list[np.ndarray]] = defaultdict(list)
        self.track_features: dict[tuple[int, int], list[np.ndarray]] = defaultdict(list)
        self.last_sample_frame: dict[tuple[int, int], int] = {}
        self.last_scores: dict[tuple[int, int], tuple[int, float]] = {}

    @staticmethod
    def _valid(vector):
        vector = np.asarray(vector, dtype=np.float32).reshape(-1)
        if vector.size == 0 or not np.isfinite(vector).all():
            return None
        norm = float(np.linalg.norm(vector))
        return vector / norm if norm > 1e-12 else None

    def add_identity_gallery(self, journey_id: int, gallery: dict) -> None:
        for key in ("original", "flipped"):
            for vector in gallery.get(key, []):
                normalized = self._valid(vector)
                if normalized is not None:
                    self.identity_gallery[int(journey_id)].append(normalized)

    def update_camera(self, camera_id: int, frame_id: int, frame, tracks) -> None:
        """Sample vehicle crops on all cameras; OCR is deliberately not part of this class."""
        images, keys = [], []
        for track_id, bbox in tracks:
            key = (int(camera_id), int(track_id))
            if frame_id - self.last_sample_frame.get(key, -self.sample_every) < self.sample_every:
                continue
            h, w = frame.shape[:2]
            x1, y1, x2, y2 = map(int, bbox)
            x1, x2 = max(0, x1), min(w, x2)
            y1, y2 = max(0, y1), min(h, y2)
            if x2 - x1 < Config.FEATURE_MIN_CROP_SIZE or y2 - y1 < Config.FEATURE_MIN_CROP_SIZE:
                continue
            crop = frame[y1:y2, x1:x2]
            if crop.size == 0:
                continue
            images.append(crop)
            keys.append(key)
            self.last_sample_frame[key] = int(frame_id)
        if not images:
            return
        try:
            vectors = self.feature_manager.extract_features(images)
        except Exception:
            logger.exception("Runtime Re-ID extraction failed on camera %s", camera_id)
            return
        for key, vector in zip(keys, vectors):
            normalized = self._valid(vector)
            if normalized is not None:
                self.track_features[key].append(normalized)

    @staticmethod
    def _score(track_features, identity_features) -> float:
        if not track_features or not identity_features:
            return -1.0
        a = np.asarray(track_features, dtype=np.float32)
        b = np.asarray(identity_features, dtype=np.float32)
        if a.ndim != 2 or b.ndim != 2 or a.shape[1] != b.shape[1]:
            return -1.0
        similarities = a @ b.T
        flat = similarities.reshape(-1)
        k = min(max(1, int(getattr(Config, "MATCH_SIM_TOPK", 5))), flat.size)
        return float(np.partition(flat, flat.size - k)[-k:].mean())

    def match_track_to_journey(self, camera_id: int, track_id: int, journey_id: int):
        track_features = self.track_features.get((int(camera_id), int(track_id)), [])
        gallery = self.identity_gallery.get(int(journey_id), [])
        if len(track_features) < self.min_samples or not gallery:
            return None
        score = self._score(track_features, gallery)
        self.last_scores[(int(camera_id), int(track_id))] = (int(journey_id), score)
        return score if score >= self.threshold else None

    def extend_identity(self, journey_id: int, camera_id: int, track_id: int) -> None:
        """Add confirmed downstream appearance samples to the same journey gallery."""
        self.add_identity_gallery(
            journey_id,
            {"original": self.track_features.get((int(camera_id), int(track_id)), []), "flipped": []},
        )

    def forget_track(self, camera_id: int, track_id: int) -> None:
        key = (int(camera_id), int(track_id))
        self.track_features.pop(key, None)
        self.last_sample_frame.pop(key, None)
        self.last_scores.pop(key, None)
