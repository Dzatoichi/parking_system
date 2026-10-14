from TrackletModule.CandidateSearch import CandidateSearch, SearchTask
from TopologyModule.CameraNetwork import CameraNetwork


def make_network():
    return CameraNetwork.from_dict({
        "frame_size": [1280, 720],
        "cameras": [
            {"id": 4, "lines": [
                {"id": 1, "p1": [100, 600], "p2": [1180, 600],
                 "peer": 5, "exit": "DOWN"},
            ]},
            {"id": 5, "lines": [
                {"id": 1, "p1": [100, 600], "p2": [1180, 600],
                 "peer": 4, "exit": "UP"},
                {"id": 2, "p1": [100, 400], "p2": [1180, 400],
                 "peer": 6, "exit": "DOWN"},
            ]},
            {"id": 6, "lines": [
                {"id": 1, "p1": [100, 400], "p2": [1180, 400],
                 "peer": 5, "exit": "UP"},
            ]},
        ],
        "segments": [],
    })


def make_task(vehicle_id=42):
    return SearchTask(
        task_id="test-task",
        vehicle_id=vehicle_id,
        source_camera=4,
        target_camera=5,
        exit_frame_id=100,
        source_track_id=17,
    )


def test_task_uses_global_vehicle_identity_when_known():
    task = make_task(42)
    assert task.vehicle_id == 42
    assert task.source_track_id == 17
    assert task.is_registered


def test_unidentified_vehicle_still_has_a_search_task():
    search = CandidateSearch(make_network(), resolve_vehicle_id=lambda cam, tid: None)
    commands = search.update(4, 100, [(17, [1, 2, 3, 4])])

    # Task creation is driven by the existing transition detector, so test the
    # task model and pending registration independently of line-crossing setup.
    task = SearchTask(
        task_id="journey:4:17:100:to:5",
        vehicle_id=None,
        source_camera=4,
        target_camera=5,
        exit_frame_id=100,
        source_track_id=17,
    )
    search.pending[task.task_id] = task
    assert task.vehicle_id is None
    assert not task.is_registered
    assert search.pending[task.task_id].source_camera == 4


def test_candidates_are_filtered_by_arrival_camera_and_movement():
    search = CandidateSearch(make_network(), resolve_vehicle_id=lambda cam, tid: 42)
    destination = search.trackers[5]

    destination._arrived_from[83] = 4
    destination._arrived_from[91] = 6
    destination.detector._motion_by_track[83] = (8.0, 0.0)
    destination.detector._motion_by_track[91] = (8.0, 0.0)
    destination.detector._motion_by_track[95] = (8.0, 0.0)
    destination._arrived_from[96] = 4
    destination.detector._motion_by_track[96] = (0.0, 0.0)

    assert search.candidates_for(make_task(), [83, 91, 95, 96]) == [83]


def test_ranker_receives_task_and_local_candidate_id():
    search = CandidateSearch(make_network(), resolve_vehicle_id=lambda cam, tid: 42)
    destination = search.trackers[5]
    destination._arrived_from[83] = 4
    destination.detector._motion_by_track[83] = (8.0, 0.0)
    task = make_task()
    calls = []

    def score(search_task, camera_id, local_track_id):
        calls.append((search_task.vehicle_id, camera_id, local_track_id))
        return 0.91

    ranked = search.rank_candidates(task, [83], score)

    assert calls == [(42, 5, 83)]
    assert ranked[0].track_id == 83
    assert ranked[0].score == 0.91


def test_unresolved_journey_can_be_attached_to_vehicle_later():
    search = CandidateSearch(make_network(), resolve_vehicle_id=lambda cam, tid: None)
    task = SearchTask(
        task_id="journey:4:17:100:to:5",
        vehicle_id=None,
        source_camera=4,
        target_camera=5,
        exit_frame_id=100,
        source_track_id=17,
    )
    search.pending[task.task_id] = task

    identified = search.attach_identity(task.task_id, vehicle_id=42)
    assert identified.vehicle_id == 42
    assert identified.task_id == task.task_id
