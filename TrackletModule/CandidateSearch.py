"""Candidate-search orchestration over the existing camera-transition algorithm.

A search belongs to a globally registered vehicle_id. Camera-local track IDs are
only observation references and are never used as vehicle identity.
"""
from dataclasses import dataclass
from typing import Callable, Iterable, Optional

from TopologyModule.CameraNetwork import CameraNetwork
from TopologyModule.TransitionTracker import (
    CommandType,
    TransitionCommand,
    TransitionTracker,
    create_trackers,
)


@dataclass(frozen=True)
class SearchTask:
    """Find a registered vehicle after a confirmed camera transition."""

    vehicle_id: int
    source_camera: int
    target_camera: int
    exit_frame_id: int
    # Diagnostic reference only; never the identity of the search.
    source_track_id: int


@dataclass(frozen=True)
class CandidateScore:
    track_id: int
    score: float


class CandidateSearch:
    """Thin coordinator around TransitionTracker, not a second transition detector.

    resolve_vehicle_id(camera_id, local_track_id) must consult the existing
    global vehicle/tracklet association. If the source track has no registered
    vehicle identity, no search task is created.

    Call update() once per frame per camera, passing all current (track_id, bbox)
    pairs. Then call candidates_for() for a task to get the destination-camera
    local tracks allowed by the existing ENTER-line logic. A caller-supplied
    scorer can rank those candidates using Re-ID, OCR and timing evidence.
    """

    def __init__(
        self,
        network: CameraNetwork,
        resolve_vehicle_id: Callable[[int, int], Optional[int]],
    ) -> None:
        self.network = network
        self.resolve_vehicle_id = resolve_vehicle_id
        self.trackers: dict[int, TransitionTracker] = create_trackers(network)
        self.pending: dict[tuple[int, int], SearchTask] = {}

    def update(
        self,
        camera_id: int,
        frame_id: int,
        tracks: Iterable[tuple[int, object]],
    ) -> list[TransitionCommand]:
        if camera_id not in self.trackers:
            raise KeyError(f"Камера {camera_id} не найдена в топологии")

        commands = self.trackers[camera_id].update(frame_id, tracks)

        for command in commands:
            if command.type is not CommandType.SEARCH_ON_CAMERA:
                continue

            # A local track is resolved to the already-registered global vehicle.
            vehicle_id = self.resolve_vehicle_id(
                command.source_camera, command.track_id
            )
            if vehicle_id is None:
                continue

            task = SearchTask(
                vehicle_id=int(vehicle_id),
                source_camera=command.source_camera,
                target_camera=command.camera_id,
                exit_frame_id=command.frame_id,
                source_track_id=command.track_id,
            )
            self.pending[(task.vehicle_id, task.target_camera)] = task

        return commands

    def candidates_for(
        self,
        task: SearchTask,
        visible_track_ids: Iterable[int],
        require_movement: bool = True,
    ) -> list[int]:
        """Return visible destination tracks whose detected entry came from source.

        Candidate IDs are local to task.target_camera. The source vehicle's
        global ID remains task.vehicle_id and is not compared to those IDs.
        """
        if not self.network.has_transition(task.source_camera, task.target_camera):
            return []

        tracker = self.trackers[task.target_camera]
        visible = {int(track_id) for track_id in visible_track_ids}
        arrived = tracker.tracks_arrived_from(task.source_camera)

        result = []
        for track_id in arrived:
            if track_id not in visible:
                continue
            if not tracker.is_eligible(track_id, task.source_camera):
                continue
            if require_movement and not tracker.detector.is_moving(track_id):
                continue
            result.append(track_id)
        return sorted(result)

    def rank_candidates(
        self,
        task: SearchTask,
        visible_track_ids: Iterable[int],
        score: Callable[[int, int, int], Optional[float]],
        require_movement: bool = True,
    ) -> list[CandidateScore]:
        """Rank allowed local tracks via score(vehicle_id, target_camera, track_id).

        The scorer is intentionally injected: this wrapper does not duplicate
        Re-ID/OCR logic or invent their weights. Missing scores are skipped.
        """
        ranked = []
        for track_id in self.candidates_for(
            task, visible_track_ids, require_movement=require_movement
        ):
            value = score(task.vehicle_id, task.target_camera, track_id)
            if value is not None:
                ranked.append(CandidateScore(track_id=track_id, score=float(value)))
        return sorted(ranked, key=lambda item: item.score, reverse=True)
