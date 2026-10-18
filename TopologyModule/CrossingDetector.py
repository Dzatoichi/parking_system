"""Детектор переходов между камерами по движению и двум границам bbox."""
from dataclasses import dataclass
from typing import Iterable, Optional

from Config import Config
from TopologyModule.CameraNetwork import Camera
from TopologyModule.TransitionLine import Role, TransitionLine


@dataclass(frozen=True)
class TransitionEvent:
    camera_id: int
    line_id: int
    track_id: int
    role: Role
    peer_camera: int
    frame_id: int
    motion: tuple[float, float]

    @property
    def from_camera(self) -> int:
        return self.camera_id if self.role is Role.EXIT else self.peer_camera

    @property
    def to_camera(self) -> int:
        return self.peer_camera if self.role is Role.EXIT else self.camera_id


@dataclass
class _CrossingState:
    """Состояние одного track ID относительно одной линии."""
    fired: bool = False
    missed: int = 0
    far_frames: int = 0
    # Anchor accumulates sub-threshold movement across frames. Without it, a
    # slow vehicle can cross the line while every individual frame is rejected.
    anchor_center: tuple[float, float] | None = None
    anchor_bbox: object | None = None
    # Last center off the line helps handle samples exactly on the line.
    last_nonzero_center: tuple[float, float] | None = None


def _center(bbox) -> tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return (x1 + x2) / 2, (y1 + y2) / 2


class CrossingDetector:
    def __init__(
            self,
            camera: Camera,
            min_move_px: Optional[float] = None,
            release_frames: Optional[int] = None,
            release_margin_px: Optional[float] = None,
            forget_frames: Optional[int] = None,
    ):
        self.camera = camera
        # Явный min_move_px оставлен для обратной совместимости.
        # По умолчанию движение нормируется на размер bbox, чтобы учитывать перспективу.
        self.min_move_px = min_move_px
        self.min_move_size_ratio = Config.TRANSITION_MIN_MOVE_SIZE_RATIO
        self.release_frames = (
            Config.TRANSITION_RELEASE_FRAMES if release_frames is None else release_frames
        )
        self.release_margin_px = (
            Config.TRANSITION_RELEASE_MARGIN_PX if release_margin_px is None else release_margin_px
        )
        self.forget_frames = Config.TRANSITION_FORGET_FRAMES if forget_frames is None else forget_frames

        self._prev_center: dict[int, tuple[float, float]] = {}
        self._prev_bbox: dict[int, object] = {}
        self._last_seen: dict[int, int] = {}
        self._states: dict[tuple[int, int], _CrossingState] = {}
        self.dropped_tracks: list[int] = []
        self._motion_by_track: dict[int, tuple[float, float]] = {}

    def update(self, frame_id: int, tracks: Iterable[tuple[int, object]]) -> list[TransitionEvent]:
        """tracks - (track_id, bbox xyxy) всех треков кадра."""
        events: list[TransitionEvent] = []
        present = set()

        for track_id, bbox in tracks:
            track_id = int(track_id)
            present.add(track_id)
            center = _center(bbox)
            prev = self._prev_center.get(track_id)
            self._motion_by_track[track_id] = (0.0, 0.0)
            prev_bbox = self._prev_bbox.get(track_id)

            if prev is not None and prev_bbox is not None:
                motion = (center[0] - prev[0], center[1] - prev[1])
                self._motion_by_track[track_id] = motion
                for line in self.camera.lines:
                    event = self._update_crossing(line, track_id, bbox, center, prev, prev_bbox, frame_id)
                    if event is not None:
                        events.append(event)

            self._prev_center[track_id] = center
            self._prev_bbox[track_id] = bbox
            self._last_seen[track_id] = frame_id

        self._release_missing(present)
        self._forget_old(frame_id)
        return events

    def is_moving(self, track_id: int) -> bool:
        """True when the latest bbox-center displacement passes the movement filter."""
        motion = self._motion_by_track.get(int(track_id), (0.0, 0.0))
        motion_length = (motion[0] ** 2 + motion[1] ** 2) ** 0.5
        if self.min_move_px is not None:
            return motion_length >= self.min_move_px
        bbox = self._prev_bbox.get(int(track_id))
        return bbox is not None and motion_length / self._bbox_diagonal(bbox) >= self.min_move_size_ratio

    @staticmethod
    def _bbox_diagonal(bbox) -> float:
        x1, y1, x2, y2 = (float(v) for v in bbox)
        width = abs(x2 - x1)
        height = abs(y2 - y1)
        return max((width * width + height * height) ** 0.5, 1.0)

    def _passes_min_movement(self, motion_length: float, previous_bbox, current_bbox) -> bool:
        # Legacy callers may still pass an absolute pixel threshold explicitly.
        if self.min_move_px is not None:
            return motion_length >= self.min_move_px
        previous_size = self._bbox_diagonal(previous_bbox)
        current_size = self._bbox_diagonal(current_bbox)
        reference_size = (previous_size + current_size) / 2.0
        return motion_length / reference_size >= self.min_move_size_ratio

    def _update_crossing(
            self,
            line: TransitionLine,
            track_id: int,
            bbox,
            center: tuple[float, float],
            prev: tuple[float, float],
            prev_bbox,
            frame_id: int,
    ):
        key = (track_id, line.line_id)
        state = self._states.setdefault(key, _CrossingState())

        # Keep an anchor until enough motion has accumulated. This makes the
        # movement filter work over a short trajectory, not just one frame.
        if state.anchor_center is None or state.anchor_bbox is None:
            state.anchor_center = prev
            state.anchor_bbox = prev_bbox

        anchor = state.anchor_center
        anchor_bbox = state.anchor_bbox
        motion = (center[0] - anchor[0], center[1] - anchor[1])
        motion_length = (motion[0] ** 2 + motion[1] ** 2) ** 0.5
        current_side = line.signed_distance(center)
        anchor_side = line.signed_distance(anchor)

        movement_ok = self._passes_min_movement(motion_length, anchor_bbox, bbox)
        alignment = line.alignment(motion)
        near_debug_line = (
            line.camera_id == 2 and line.peer_camera == 9
            and (abs(anchor_side) <= 160 or abs(current_side) <= 160
                 or anchor_side * current_side < 0)
        )

        # Check accumulated motion before advancing the anchor. If the center
        # has reached the other side but motion is still sub-threshold, retain
        # the original-side anchor so the crossing remains observable.
        opposite_sides = anchor_side * current_side < 0
        if not movement_ok or alignment < Config.TRANSITION_MIN_MOTION_ALIGNMENT:
            if near_debug_line:
                print(
                    f"[TRANSITION DEBUG] camera=2 target=9 frame={frame_id} track={track_id} "
                    f"line={line.line_id} reject={'movement' if not movement_ok else 'alignment'} "
                    f"prev_center=({prev[0]:.1f},{prev[1]:.1f}) "
                    f"center=({center[0]:.1f},{center[1]:.1f}) "
                    f"motion=({motion[0]:.1f},{motion[1]:.1f}) "
                    f"distance=({anchor_side:.1f}->{current_side:.1f}) "
                    f"move_px={motion_length:.2f} alignment={alignment:.3f} "
                    f"required_alignment={Config.TRANSITION_MIN_MOTION_ALIGNMENT:.3f} "
                    f"move_ratio={motion_length / ((self._bbox_diagonal(anchor_bbox) + self._bbox_diagonal(bbox)) / 2.0):.4f} "
                    f"required_move_ratio={self.min_move_size_ratio:.4f} fired={state.fired}"
                )
            if abs(current_side) > 1e-9:
                state.last_nonzero_center = center
            # Do not advance the anchor across the line while movement is
            # below threshold; otherwise a slow crossing is lost permanently.
            if not opposite_sides and movement_ok:
                state.anchor_center = center
                state.anchor_bbox = bbox
            if state.fired:
                self._update_release_state(state, abs(current_side))
            return None

        # After an event, wait for a meaningful, sustained departure from the line
        # before allowing another event for the same track and line.
        if state.fired:
            if near_debug_line:
                print(
                    f"[TRANSITION DEBUG] camera=2 target=9 frame={frame_id} track={track_id} "
                    f"line={line.line_id} reject=already_fired distance={current_side:.1f} "
                    f"fired_frames={state.far_frames}"
                )
            self._update_release_state(state, abs(current_side))
            if abs(current_side) > 1e-9:
                state.last_nonzero_center = center
            state.anchor_center = center
            state.anchor_bbox = bbox
            return None

        # If the anchor was exactly on the line, use the last definite-side
        # sample as the origin rather than treating a touch as a crossing.
        crossing_origin = anchor
        if abs(anchor_side) <= 1e-9 and state.last_nonzero_center is not None:
            crossing_origin = state.last_nonzero_center

        center_crossed = line.center_crosses(crossing_origin, center)
        bbox_jumped = line.bbox_crosses_between(anchor_bbox, bbox, motion)
        if not center_crossed and not bbox_jumped:
            if near_debug_line:
                print(
                    f"[TRANSITION DEBUG] camera=2 target=9 frame={frame_id} track={track_id} "
                    f"line={line.line_id} reject=geometry center_crossed={center_crossed} "
                    f"bbox_jumped={bbox_jumped} "
                    f"prev_center=({prev[0]:.1f},{prev[1]:.1f}) "
                    f"center=({center[0]:.1f},{center[1]:.1f}) "
                    f"distance=({anchor_side:.1f}->{current_side:.1f}) "
                    f"alignment={alignment:.3f}"
                )
            if abs(current_side) > 1e-9:
                state.last_nonzero_center = center
            # Motion was large enough but did not cross this finite segment;
            # start a fresh accumulation window at the current observation.
            state.anchor_center = center
            state.anchor_bbox = bbox
            return None

        state.fired = True
        state.far_frames = 0
        if abs(current_side) > 1e-9:
            state.last_nonzero_center = center
        state.anchor_center = center
        state.anchor_bbox = bbox

        return TransitionEvent(
            camera_id=line.camera_id,
            line_id=line.line_id,
            track_id=track_id,
            role=line.role_of_motion(motion),
            peer_camera=line.peer_camera,
            frame_id=frame_id,
            motion=motion,
        )

    def _update_release_state(self, state: _CrossingState, current_distance: float) -> None:
        if current_distance >= self.release_margin_px:
            state.far_frames += 1
            if state.far_frames >= self.release_frames:
                state.fired = False
                state.far_frames = 0
        else:
            state.far_frames = 0

    def _release_missing(self, present: set) -> None:
        for (track_id, line_id), state in list(self._states.items()):
            if track_id not in present:
                state.missed += 1
                if state.missed >= self.release_frames:
                    del self._states[(track_id, line_id)]
            else:
                state.missed = 0

    def _forget_old(self, frame_id: int) -> None:
        self.dropped_tracks = [
            track_id for track_id, seen in self._last_seen.items()
            if frame_id - seen >= self.forget_frames
        ]
        for track_id in self.dropped_tracks:
            self._last_seen.pop(track_id, None)
            self._prev_center.pop(track_id, None)
            self._prev_bbox.pop(track_id, None)
            self._motion_by_track.pop(track_id, None)
            for key in [k for k in self._states if k[0] == track_id]:
                del self._states[key]
