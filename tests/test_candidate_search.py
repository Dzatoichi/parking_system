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


def test_task_identity_is_global_vehicle_not_local_track():
    task = SearchTask(
        vehicle_id=42,
        source_camera=4,
        target_camera=5,
        exit_frame_id=100,
        source_track_id=17,
    )

    assert task.vehicle_id == 42
    assert task.source_track_id == 17
    assert task.vehicle_id != task.source_track_id


def test_candidates_are_filtered_by_arrival_camera_and_movement():
    search = CandidateSearch(make_network(), resolve_vehicle_id=lambda cam, tid: 42)
    destination = search.trackers[5]

    # These states are the same state maintained by TransitionTracker after
    # it detects ENTER-line crossings; track 83 came from 4, track 91 from 6.
    destination._arrived_from[83] = 4
    destination._arrived_from[91] = 6
    destination.detector._motion_by_track[83] = (8.0, 0.0)
    destination.detector._motion_by_track[91] = (8.0, 0.0)
    destination.detector._motion_by_track[95] = (8.0, 0.0)
    destination._arrived_from[96] = 4
    destination.detector._motion_by_track[96] = (0.0, 0.0)

    task = SearchTask(
        vehicle_id=42,
        source_camera=4,
        target_camera=5,
        exit_frame_id=100,
        source_track_id=17,
    )

    assert search.candidates_for(task, [83, 91, 95, 96]) == [83]


def test_ranker_receives_global_vehicle_id_and_local_candidate_id():
    search = CandidateSearch(make_network(), resolve_vehicle_id=lambda cam, tid: 42)
    destination = search.trackers[5]
    destination._arrived_from[83] = 4
    destination.detector._motion_by_track[83] = (8.0, 0.0)

    task = SearchTask(
        vehicle_id=42,
        source_camera=4,
        target_camera=5,
        exit_frame_id=100,
        source_track_id=17,
    )
    calls = []

    def score(vehicle_id, camera_id, local_track_id):
        calls.append((vehicle_id, camera_id, local_track_id))
        return 0.91

    ranked = search.rank_candidates(task, [83], score)

    assert calls == [(42, 5, 83)]
    assert ranked[0].track_id == 83
    assert ranked[0].score == 0.91
