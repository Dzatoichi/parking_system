"""Candidate-search orchestration over the existing camera-transition algorithm.

A search follows a registered vehicle or an unresolved journey. Local track IDs
are observation references, never global vehicle identity.
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
    """A journey; vehicle_id remains absent until identity is established."""

    task_id: str
    vehicle_id: Optional[int]
    source_camera: int
    target_camera: int
    exit_frame_id: int
    source_track_id: int

    @property
    def is_registered(self) -> bool:
        return self.vehicle_id is not None


@dataclass(frozen=True)
class CandidateScore:
    track_id: int
    score: float


class CandidateSearch:
    """Coordinate camera handoffs; leave Re-ID/OCR scoring to the caller.

    Only moving, topology-eligible tracks are considered as *new candidates*.
    If exactly one candidate is present, it can be confirmed by exclusivity
    without Re-ID/OCR. When several candidates exist, the caller can rank them.
    Once confirmed, an observation remains active even when its vehicle stops.
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
        self.active_by_track: dict[tuple[int, int], SearchTask] = {}

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

            source_key = (command.source_camera, command.track_id)
            active_task = self.active_by_track.pop(source_key, None)
            resolved_id = self.resolve_vehicle_id(
                command.source_camera, command.track_id
            )
            vehicle_id = (
                active_task.vehicle_id
                if active_task is not None and active_task.vehicle_id is not None
                else resolved_id
            )

            # Keep the same journey identity across camera-local track ID changes.
            if active_task is not None:
                task_id = active_task.task_id
            elif vehicle_id is not None:
                task_id = (
                    f"vehicle:{vehicle_id}:from:{command.source_camera}:"
                    f"track:{command.track_id}:frame:{command.frame_id}"
                )
            else:
                task_id = (
                    f"journey:{command.source_camera}:{command.track_id}:"
                    f"{command.frame_id}"
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
        """Return eligible moving tracks that entered target_camera from source."""
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
            # Movement is a gate for initial candidate selection only.
            if require_movement and not tracker.detector.is_moving(track_id):
                continue
            result.append(track_id)
        return sorted(result)

    def confirm_unique_candidate(
        self, task_id: str, visible_track_ids: Iterable[int]
    ) -> Optional[int]:
        """Confirm the sole eligible moving candidate without invoking Re-ID/OCR.

        Returns its camera-local track ID when exactly one candidate exists.
        Returns None for zero or multiple candidates; the caller can then wait or
        invoke Re-ID/OCR scoring to resolve ambiguity.
        """
        task = self.pending[task_id]
        candidates = self.candidates_for(task, visible_track_ids)
        if len(candidates) != 1:
            return None
        self.confirm_candidate(task_id, candidates[0])
        return candidates[0]

    def rank_candidates(
        self,
        task: SearchTask,
        visible_track_ids: Iterable[int],
        score: Callable[[SearchTask, int, int], Optional[float]],
        require_movement: bool = True,
    ) -> list[CandidateScore]:
        """Rank candidates with score(task, target_camera, local_track_id)."""
        ranked = []
        for track_id in self.candidates_for(
            task, visible_track_ids, require_movement=require_movement
        ):
            value = score(task, task.target_camera, track_id)
            if value is not None:
                ranked.append(CandidateScore(track_id=track_id, score=float(value)))
        return sorted(ranked, key=lambda item: item.score, reverse=True)

    def confirm_candidate(
        self, task_id: str, target_track_id: int
    ) -> SearchTask:
        """Confirm a moving eligible candidate and keep following it if it stops."""
        task = self.pending[task_id]
        tracker = self.trackers[task.target_camera]
        if not tracker.is_eligible(target_track_id, task.source_camera):
            raise ValueError("Трек не пересёк входную линию от ожидаемой камеры")
        if not tracker.detector.is_moving(target_track_id):
            raise ValueError("Новый кандидат должен двигаться в момент подтверждения")

        self.active_by_track[(task.target_camera, int(target_track_id))] = task
        return task

    def active_tracks(
        self, camera_id: int, visible_track_ids: Iterable[int]
    ) -> dict[int, SearchTask]:
        """Return confirmed visible tracks, including currently stationary vehicles.

        Do not apply the candidate movement filter here: after confirmation,
        maintaining identity and following the vehicle to its parking place takes
        priority over whether it is moving in this frame.
        """
        visible = {int(track_id) for track_id in visible_track_ids}
        return {
            track_id: task
            for (cam_id, track_id), task in self.active_by_track.items()
            if cam_id == camera_id and track_id in visible
        }

    def attach_identity(self, task_id: str, vehicle_id: int) -> SearchTask:
        """Attach a newly established global identity to an unresolved journey."""
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

        for key, active_task in list(self.active_by_track.items()):
            if active_task.task_id == task_id:
                self.active_by_track[key] = identified
        return identified
