from enum import Enum

import numpy as np
from typing import Optional, Dict


class Tracklet:
    _tracklet = -1

    def __init__(self, cam_id: int, track_id: int, bbox, feature: np.ndarray):
        self.tracklet_id: int = self._get_tracklet_id()

        self.cam_id: int = cam_id
        self.bbox = bbox

        self.last_reid_frame: int = -1

        self.current_track_id: int = track_id

        self.vehicle_id: Optional[int] = None

        self.features: list[np.ndarray] = []
        self.mean_feature: Optional[np.ndarray] = None
        self.update_feature(feature)

        self.match_count_by_vehicle_id: Dict[int, int] = {}
        self.lost_counter = 0

        self.state: TrackletState = TrackletState.UNMATCHED

    @classmethod
    def _get_tracklet_id(cls) -> int:
        cls._tracklet += 1
        return cls._tracklet

    def update_feature(self, feature):
        self.features.append(feature)
        self.features = self.features[-5:]
        self.mean_feature = np.mean(self.features, axis=0)

    def should_reid(self, frame_id: int) -> bool:
        if self.state == TrackletState.UNMATCHED:
            return frame_id - self.last_reid_frame >= 10

        if self.state == TrackletState.CANDIDATE:
            return frame_id - self.last_reid_frame >= 3

        if self.state == TrackletState.CONFIRMED:
            return frame_id - self.last_reid_frame >= 30

        if self.state == TrackletState.LOST:
            return frame_id - self.last_reid_frame >= 10

        return False

    def mark_reid(self, frame_id: int):
        self.last_reid_frame = frame_id


class TrackletState(Enum):
    UNMATCHED = 0
    CANDIDATE = 1
    CONFIRMED = 2
    LOST = 3
