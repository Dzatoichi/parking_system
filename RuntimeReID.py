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
        self.last_diagnostic_scores: dict[tuple[int, int], float] = {}
        self.last_diagnostic_matches: dict[tuple[int, int], tuple[float, int, str]] = {}
        # Avoid printing the same comparison on every video frame.
        self._last_match_log_state: dict[tuple[int, int, int], tuple] = {}

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

    def update_camera(self, camera_id: int, frame_id: int, frame, tracks) -> list[tuple[int, np.ndarray]]:
        """Sample only the supplied (already movement-filtered) tracks."""
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
            return []
        try:
            vectors = self.feature_manager.extract_features(images)
        except Exception:
            logger.exception("Runtime Re-ID extraction failed on camera %s", camera_id)
            return []
        accepted = []
        duplicate_threshold = float(
            getattr(Config, "RUNTIME_REID_DUPLICATE_THRESHOLD", 0.90)
        )
        for key, vector in zip(keys, vectors):
            normalized = self._valid(vector)
            if normalized is None:
                continue
            gallery = self.track_features[key]
            # Adaptive sampling: compare only with the last accepted view. Do not
            # advance the reference when a near-duplicate is rejected.
            if gallery and float(np.dot(normalized, gallery[-1])) >= duplicate_threshold:
                continue
            gallery.append(normalized)
            accepted.append((key[1], normalized.copy()))
        return accepted

    @staticmethod
    def _similarity_scores(track_features, identity_features) -> tuple[float, float]:
        """Return (best pairwise cosine similarity, mean of top-k similarities)."""
        if not track_features or not identity_features:
            return -1.0, -1.0
        a = np.asarray(track_features, dtype=np.float32)
        b = np.asarray(identity_features, dtype=np.float32)
        if a.ndim != 2 or b.ndim != 2 or a.shape[1] != b.shape[1]:
            return -1.0, -1.0
        flat = (a @ b.T).reshape(-1)
        best = float(np.max(flat))
        k = min(max(1, int(getattr(Config, "MATCH_SIM_TOPK", 5))), flat.size)
        mean_topk = float(np.partition(flat, flat.size - k)[-k:].mean())
        return best, mean_topk

    def log_feature_against_all_identities(
        self, camera_id: int, track_id: int, query_feature, identity_labels: dict[int, str]
    ) -> None:
        """Log one new local-track vector against every registered identity gallery.

        For each identity, best_sim is the maximum cosine similarity between this
        single query vector and all vectors stored in that identity's gallery.
        This is diagnostic only; it does not assign or change the vehicle identity.
        """
        query = self._valid(query_feature)
        if query is None:
            return
        comparisons = []
        for journey_id, gallery in self.identity_gallery.items():
            if not gallery:
                continue
            best_sim, _ = self._similarity_scores([query], gallery)
            plate = str(identity_labels.get(int(journey_id), "UNKNOWN"))
            comparisons.append((best_sim, int(journey_id), plate, len(gallery)))
        comparisons.sort(key=lambda item: item[0], reverse=True)
        if comparisons:
            best_sim, best_journey_id, best_plate, _gallery_count = comparisons[0]
            key = (int(camera_id), int(track_id))
            self.last_diagnostic_scores[key] = float(best_sim)
            self.last_diagnostic_matches[key] = (
                float(best_sim), int(best_journey_id), str(best_plate)
            )

    def match_track_to_journey(self, camera_id: int, track_id: int, journey_id: int):
        camera_id, track_id, journey_id = int(camera_id), int(track_id), int(journey_id)
        track_features = self.track_features.get((camera_id, track_id), [])
        gallery = self.identity_gallery.get(journey_id, [])
        log_key = (camera_id, track_id, journey_id)

        if len(track_features) < self.min_samples or not gallery:
            state = (len(track_features), len(gallery), None, "INSUFFICIENT_FEATURES")
            if self._last_match_log_state.get(log_key) != state:
                print(
                    f"[REID SIM] camera={camera_id} track={track_id} journey={journey_id} "
                    f"sim=NA track_features={len(track_features)} "
                    f"journey_features={len(gallery)} min_track_features={self.min_samples} "
                    f"result=INSUFFICIENT_FEATURES"
                )
                self._last_match_log_state[log_key] = state
            return None

        # Evaluate the newest accepted observation only against every registered
        # gallery embedding. Do not let an old target-frame embedding keep the
        # displayed score artificially unchanged as the vehicle changes view.
        query_feature = track_features[-1:]
        best_score, mean_topk_score = self._similarity_scores(query_feature, gallery)
        # Brute-force gallery search: the best single pair determines the decision.
        score = best_score
        self.last_scores[(camera_id, track_id)] = (journey_id, score)
        result = "ACCEPT" if score >= self.threshold else "REJECT"
        # Feature counts change only when a new appearance sample is accepted, so
        # this prints useful score updates without flooding the log every frame.
        state = (
            len(track_features), len(gallery), round(float(best_score), 3),
            round(float(mean_topk_score), 3), result
        )
        if self._last_match_log_state.get(log_key) != state:
            self._last_match_log_state[log_key] = state
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
        self.last_diagnostic_scores.pop(key, None)
        self.last_diagnostic_matches.pop(key, None)
