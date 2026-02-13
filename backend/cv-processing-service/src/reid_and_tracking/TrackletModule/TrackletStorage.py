from typing import Dict

from TrackletModule.Tracklet import Tracklet, TrackletState


class TrackletStorage:
    def __init__(self):
        self.unmatched: Dict[int, Tracklet] = {}
        self.unconfirmed: Dict[int, Tracklet] = {}
        self.confirmed: Dict[int, Tracklet] = {}

    def add_tracklet(self, tracklet: Tracklet) -> None:
        self.unmatched[tracklet.current_track_id] = tracklet

    def unmatched_2_unconfirmed(self, tracklet: Tracklet, vehicle_id: int) -> None:
        tracklet.state = TrackletState.CANDIDATE
        tracklet.match_count_by_vehicle_id[vehicle_id] = 1

        self.unconfirmed[tracklet.current_track_id] = tracklet
        self.unmatched.pop(tracklet.current_track_id)

    def unconfirmed_2_confirmed(self, tracklet: Tracklet, vehicle_id: int) -> None:
        tracklet.vehicle_id = vehicle_id
        tracklet.state = TrackletState.CONFIRMED
        tracklet.match_count_by_vehicle_id = {}

        # Удаляем vehicle_id из мэтчинга у остальных
        for track_id, unconfirmed_tracklet in self.unconfirmed.items():
            if vehicle_id in unconfirmed_tracklet.match_count_by_vehicle_id:
                unconfirmed_tracklet.match_count_by_vehicle_id.pop(vehicle_id, None)

        self.confirmed[tracklet.current_track_id] = tracklet
        self.unconfirmed.pop(tracklet.current_track_id)

    def confirmed_2_unconfirmed(self, tracklet: Tracklet):
        tracklet.state = TrackletState.CANDIDATE
        tracklet.match_count_by_vehicle_id[tracklet.vehicle_id] = 1

        tracklet.vehicle_id = None
        tracklet.lost_counter = 0

        self.unconfirmed[tracklet.current_track_id] = tracklet
        self.confirmed.pop(tracklet.current_track_id)




