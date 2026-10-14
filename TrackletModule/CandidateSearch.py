"""Candidate-search orchestration over the existing camera-transition algorithm.

A search can follow either a registered global vehicle or an unresolved journey.
Camera-local track IDs are observation references, never global vehicle identity.
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
    """A search journey; vehicle_id is absent until identity is established."""

    task_id: str
    vehicle_id: Optional[int]
    source_camera: int
    target_camera: int
    exit_frame_id: int
    # Diagnostic observation reference, not the identity of the task.
    source_track_id: int

    @property
    def is_registered(self) -> bool:
        return self.vehicle_id is not None


@dataclass(frozen=True)
class CandidateScore:
    track_id: int
    score: float


class CandidateSearch:
    """Thin coordinator around the existing TransitionTracker.

    Registered path:
      source local track -> resolver returns vehicle_id -> task follows vehicle.

    Unresolved path:
      resolver returns None -> task still follows a temporary journey key built
      from the source camera/track/exit frame. At the destination, candidate
      observations can be ranked using source/destination features. If a match
      is established, the caller may attach the resulting local track to a
      global vehicle ID; if not, the journey can continue to the next camera.

    The class does not implement Re-ID/OCR scoring or a new transition detector.
    """

    def __init__(
        self,
        network: CameraNetwork,
        resolve_vehicle_id: Callable[[int, int], Optional[int]],
    ) -> None:
        self.network = network
        self.resolve_vehicle_id = resolve_vehicle_id
        self.trackers: dict[int, TransitionTracker] = create_trackers(network)
        self.pending: dict[str, SearchTask] = {}

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

            vehicle_id = self.resolve_vehicle_id(
                command.source_camera, command.track_id
            )
            # A journey exists even when no global identity can be resolved.
            # Include exit frame so a later passage by the same local tracker
            # creates a distinct journey.
            task_id = (
                f"vehicle:{vehicle_id}:to:{command.camera_id}:"
                f"frame:{command.frame_id}"
                if vehicle_id is not None
                else f"journey:{command.source_camera}:{command.track_id}:"
                     f"{command.frame_id}:to:{command.camera_id}"
            )

            task = SearchTask(
                task_id=task_id,
                vehicle_id=int(vehicle_id) if vehicle_id is not None else None,
                source_camera=command.source_camera,
                target_camera=command.camera_id,
                exit_frame_id=command.frame_id,
                source_track_id=command.track_id,
            )
            self.pending[task.task_id] = task

        return commands

    def candidates_for(
        self,
        task: SearchTask,
        visible_track_ids: Iterable[int],
        require_movement: bool = True,
    ) -> list[int]:
        """Return visible target-camera tracks with a confirmed entry from source."""
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
        score: Callable[[SearchTask, int, int], Optional[float]],
        require_movement: bool = True,
    ) -> list[CandidateScore]:
        """Rank candidates using score(task, target_camera, local_track_id).

        The scorer can compare stored global-vehicle features when vehicle_id is
        known, or source-observation/journey features when it is not. The same
        topology/movement filters apply in both cases.
        """
        ranked = []
        for track_id in self.candidates_for(
            task, visible_track_ids, require_movement=require_movement
        ):
            value = score(task, task.target_camera, track_id)
            if value is not None:
                ranked.append(CandidateScore(track_id=track_id, score=float(value)))
        return sorted(ranked, key=lambda item: item.score, reverse=True)

    def attach_identity(self, task_id: str, vehicle_id: int) -> SearchTask:
        """Mark a previously unresolved journey as identified.

        Persistence/track association is deliberately delegated to the caller.
        """
        task = self.pending[task_id]
        identified = SearchTask(
            task_id=task.task_id,
            vehicle_id=int(vehicle_id),
            source_camera=task.source_camera,
            target_camera=task.target_camera,
            exit_frame_id=task.exit_frame_id,
            source_track_id=task.source_track_id,
        )
        self.pending[task_id] = identified
        return identified
