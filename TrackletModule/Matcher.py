import logging
from typing import Dict, Iterable, Optional

import numpy as np

from Config import Config
from FeaturesModule.FeaturesManager import FeaturesManager
from TrackletModule.FindStorage import FindStorage
from TrackletModule.Tracklet import Tracklet, TrackletState
from TrackletModule.TrackletStorage import TrackletStorage

logger = logging.getLogger(__name__)


class Matcher:
    """Batch Re-ID matcher.

    Gallery embeddings are normalized once per matching call. Similarities are
    computed with matrix multiplication in bounded tracklet chunks; identity
    scores aggregate the best few cross-view comparisons instead of trusting a
    single lucky pair.
    """

    def __init__(
        self,
        feature_manager: FeaturesManager,
        tracklet_storage: TrackletStorage,
        find_storage: FindStorage,
        similarity_threshold: float = 0.92,
        frames_for_confirm: int = 3,
        frames_for_lost: int = 5,
    ):
        if not -1.0 <= similarity_threshold <= 1.0:
            raise ValueError("similarity_threshold должен быть в диапазоне [-1, 1]")
        if frames_for_confirm < 1 or frames_for_lost < 1:
            raise ValueError("frames_for_confirm и frames_for_lost должны быть >= 1")

        self.fm = feature_manager
        self.t_storage = tracklet_storage
        self.f_storage = find_storage
        self.similarity_threshold = float(similarity_threshold)
        self.frames_for_confirm = int(frames_for_confirm)
        self.frames_for_lost = int(frames_for_lost)

    def _scope(
        self,
        state: TrackletState,
        track_ids: Optional[Iterable],
    ) -> Dict[int, Tracklet]:
        """Only compare tracklets whose Re-ID features were updated this cycle."""
        storage = self.t_storage.storage[state]
        if track_ids is None:
            return dict(storage)
        return {track_id: storage[track_id] for track_id in track_ids if track_id in storage}

    @staticmethod
    def _normalize(vectors) -> np.ndarray:
        matrix = np.asarray(vectors, dtype=np.float32)
        if matrix.size == 0:
            return np.empty((0, 0), dtype=np.float32)
        matrix = np.atleast_2d(matrix)
        matrix = np.nan_to_num(matrix, copy=False, nan=0.0, posinf=0.0, neginf=0.0)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        return np.divide(matrix, np.maximum(norms, 1e-12), out=np.zeros_like(matrix), where=norms > 1e-12)

    @staticmethod
    def _aggregate(similarities: np.ndarray) -> float:
        """Aggregate pairwise cosine scores for one vehicle/tracklet pair."""
        flat = np.asarray(similarities, dtype=np.float32).ravel()
        if flat.size == 0:
            return -1.0
        if Config.MATCH_SIM_AGGREGATION == "topk_mean":
            k = min(max(1, int(Config.MATCH_SIM_TOPK)), flat.size)
            # partition avoids sorting the full matrix when galleries are large
            return float(np.partition(flat, flat.size - k)[-k:].mean())
        if Config.MATCH_SIM_AGGREGATION == "mean":
            return float(flat.mean())
        # Kept as an explicit compatibility mode, but not the production default.
        return float(flat.max())

    @classmethod
    def _pair_similarity(cls, tracklet_features, vehicle_features) -> float:
        if tracklet_features is None or vehicle_features is None:
            return -1.0
        if len(tracklet_features) == 0 or len(vehicle_features) == 0:
            return -1.0
        track_matrix = cls._normalize(tracklet_features)
        vehicle_matrix = cls._normalize(vehicle_features)
        if track_matrix.shape[1] != vehicle_matrix.shape[1]:
            logger.warning(
                "Re-ID dimension mismatch: tracklet=%s gallery=%s",
                track_matrix.shape[1], vehicle_matrix.shape[1],
            )
            return -1.0
        return cls._aggregate(track_matrix @ vehicle_matrix.T)

    def matching_unmatched_tracklets(self, track_ids: Optional[Iterable] = None) -> None:
        tracklets = self._scope(TrackletState.MOVE_UNMATCHED, track_ids)
        result_pairs = self._match(self.f_storage.searched, tracklets)
        for vehicle_id, tracklet in result_pairs:
            logger.info(
                "Re-ID candidate: vehicle=%s camera=%s track=%s",
                vehicle_id, tracklet.cam_id, tracklet.track_id,
            )
            self.t_storage.move_2_candidate(vehicle_id=vehicle_id, tracklet=tracklet)

    def matching_candidate_tracklets(self, track_ids: Optional[Iterable] = None) -> None:
        tracklets = self._scope(TrackletState.CANDIDATE, track_ids)
        result_pairs = self._match(self.f_storage.searched, tracklets)
        matched_vehicle_by_tracklet = {
            tracklet.tracklet_id: vehicle_id for vehicle_id, tracklet in result_pairs
        }

        penalty = max(1, int(Config.CANDIDATE_MISS_PENALTY))
        for tracklet in list(tracklets.values()):
            counts = tracklet.match_count_by_vehicle_id
            matched_vehicle_id = matched_vehicle_by_tracklet.get(tracklet.tracklet_id)

            # A candidate's evidence must be consecutive (or decay after misses).
            for vehicle_id in list(counts):
                if vehicle_id == matched_vehicle_id:
                    continue
                counts[vehicle_id] -= penalty
                if counts[vehicle_id] <= 0:
                    del counts[vehicle_id]

            if matched_vehicle_id is not None:
                counts[matched_vehicle_id] = counts.get(matched_vehicle_id, 0) + 1
                if counts[matched_vehicle_id] >= self.frames_for_confirm:
                    logger.info(
                        "Re-ID confirmed: vehicle=%s camera=%s track=%s",
                        matched_vehicle_id, tracklet.cam_id, tracklet.track_id,
                    )
                    self.t_storage.candidate_2_confirmed(
                        tracklet=tracklet, vehicle_id=matched_vehicle_id
                    )
                    self.f_storage.vehicle_found(vehicle_id=matched_vehicle_id)
                    continue

            if tracklet.state is TrackletState.CANDIDATE and not counts:
                self.t_storage.candidate_2_unmatched(tracklet=tracklet)

    def matching_confirmed_tracklets(self, track_ids: Optional[Iterable] = None) -> None:
        """Validate each confirmed track only against its assigned vehicle gallery.

        A confirmed identity must not be reassigned by a global greedy matching
        against other found vehicles.
        """
        tracklets = self._scope(TrackletState.CONFIRMED, track_ids)
        for tracklet in list(tracklets.values()):
            vehicle_id = tracklet.vehicle_id
            gallery = self.f_storage.found.get(vehicle_id) if vehicle_id is not None else None
            similarity = self._pair_similarity(tracklet.features, gallery)
            matched = similarity >= self.similarity_threshold

            if not matched:
                tracklet.lost_counter += 1
                if tracklet.lost_counter >= self.frames_for_lost:
                    logger.info(
                        "Re-ID lost: vehicle=%s camera=%s track=%s score=%.4f",
                        vehicle_id, tracklet.cam_id, tracklet.track_id, similarity,
                    )
                    self.t_storage.confirmed_2_candidate(tracklet=tracklet)
                    self.f_storage.vehicle_lost(vehicle_id=vehicle_id)
            else:
                tracklet.lost_counter = max(0, tracklet.lost_counter - 1)

    def _match(
        self,
        vehicles: Dict[int, list[np.ndarray]],
        tracklets: Dict[int, Tracklet],
    ) -> list[tuple[int, Tracklet]]:
        """Batch cosine comparisons while bounding temporary gallery memory."""
        if not vehicles or not tracklets:
            return []

        valid_tracklets = []
        feature_dim = None
        for tracklet in tracklets.values():
            if not tracklet.features:
                continue
            matrix = self._normalize(tracklet.features)
            if matrix.size == 0:
                continue
            if feature_dim is None:
                feature_dim = matrix.shape[1]
            if matrix.shape[1] != feature_dim:
                logger.warning(
                    "Skipping tracklet camera=%s track=%s: inconsistent feature dimension",
                    tracklet.cam_id, tracklet.track_id,
                )
                continue
            valid_tracklets.append((tracklet, matrix))

        if not valid_tracklets:
            return []

        # Normalize each car's gallery once. Keep galleries separate so a large
        # fleet does not create one enormous concatenated embedding matrix.
        galleries = {}
        for vehicle_id, features in vehicles.items():
            if features is None or len(features) == 0:
                continue
            matrix = self._normalize(features)
            if matrix.size == 0:
                continue
            if matrix.shape[1] != feature_dim:
                logger.warning(
                    "Skipping vehicle %s: gallery dimension %s != tracklet dimension %s",
                    vehicle_id, matrix.shape[1], feature_dim,
                )
                continue
            galleries[vehicle_id] = matrix

        if not galleries:
            return []

        tracklet_batch_size = max(1, int(getattr(Config, "MATCH_TRACKLET_BATCH_SIZE", 32)))
        vehicle_batch_size = max(1, int(getattr(Config, "MATCH_VEHICLE_BATCH_SIZE", 32)))
        vehicle_items = list(galleries.items())
        candidates = []

        for track_offset in range(0, len(valid_tracklets), tracklet_batch_size):
            track_chunk = valid_tracklets[track_offset:track_offset + tracklet_batch_size]
            flat_features = []
            row_owner = []
            for local_idx, (_, matrix) in enumerate(track_chunk):
                flat_features.extend(matrix)
                row_owner.extend([local_idx] * len(matrix))
            track_matrix = np.asarray(flat_features, dtype=np.float32)
            row_owner = np.asarray(row_owner, dtype=np.int32)

            for vehicle_offset in range(0, len(vehicle_items), vehicle_batch_size):
                vehicle_chunk = vehicle_items[vehicle_offset:vehicle_offset + vehicle_batch_size]
                flat_gallery = []
                gallery_slices = {}
                cursor = 0
                for vehicle_id, gallery in vehicle_chunk:
                    flat_gallery.extend(gallery)
                    gallery_slices[vehicle_id] = (cursor, cursor + len(gallery))
                    cursor += len(gallery)

                gallery_matrix = np.asarray(flat_gallery, dtype=np.float32)
                similarities = track_matrix @ gallery_matrix.T

                for local_idx, (tracklet, _) in enumerate(track_chunk):
                    rows = np.flatnonzero(row_owner == local_idx)
                    for vehicle_id, (column_start, column_end) in gallery_slices.items():
                        score = self._aggregate(
                            similarities[np.ix_(rows, np.arange(column_start, column_end))]
                        )
                        logger.debug(
                            "Re-ID score vehicle=%s camera=%s track=%s score=%.4f",
                            vehicle_id, tracklet.cam_id, tracklet.track_id, score,
                        )
                        if score >= self.similarity_threshold:
                            candidates.append((vehicle_id, tracklet, score))

        # Greedy one-to-one assignment prevents a gallery or tracklet being claimed twice.
        candidates.sort(key=lambda item: item[2], reverse=True)
        used_vehicle_ids = set()
        used_tracklet_ids = set()
        pairs = []
        for vehicle_id, tracklet, score in candidates:
            if vehicle_id in used_vehicle_ids or tracklet.tracklet_id in used_tracklet_ids:
                continue
            pairs.append((vehicle_id, tracklet))
            used_vehicle_ids.add(vehicle_id)
            used_tracklet_ids.add(tracklet.tracklet_id)
            logger.debug(
                "Re-ID pair vehicle=%s camera=%s track=%s score=%.4f",
                vehicle_id, tracklet.cam_id, tracklet.track_id, score,
            )
        return pairs
