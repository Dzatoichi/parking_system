from typing import Dict

from TrackletModule.Tracklet import Tracklet
from TrackletModule.TrackletStorage import TrackletStorage
from TrackletModule.Matcher import Matcher
from FeaturesModule.FeaturesManager import FeaturesManager
from TrackletModule.FindStorage import FindStorage
from DB.database_manager import DatabaseManager
from DB.features.feature_repository import CarFeatureRepository
from Config import Settings


class TrackletManager:
    def __init__(self, cam_id: int, similarity_threshold, frames_for_confirm, frames_for_lost):
        self.cam_id: int = cam_id
        self.similarity_threshold = similarity_threshold
        self.frames_for_confirm = frames_for_confirm
        self.frames_for_lost = frames_for_lost

        self.feats_manager = FeaturesManager(Settings.OSNET_MODEL_PATH)

        self.matcher: Matcher = Matcher(
            features_manager=self.feats_manager,
            similarity_threshold=self.similarity_threshold,
            frames_for_confirm=self.frames_for_confirm
        )

        self.t_storage = TrackletStorage()

        db_manager = DatabaseManager(
            database=Settings.DB_NAME,
            user=Settings.DB_USER,
            password=Settings.DB_PASS,
            host=Settings.DB_HOST,
            port=Settings.DB_PORT,
        )
        db_manager.connect()
        self.car_feature_repository = CarFeatureRepository(db_manager=db_manager)

        self.tracks = {
            "tracks_ids": [],
            "tracks_bboxes": []
        }

        self.f_storage = FindStorage()

        self.known_track_ids: set[int] = set()

    def update(self, byte_track_bboxes, byte_track_ids, frame_id, frame):
        new_tracks = []
        unmatched_tracks = []
        unconfirmed_tracks = []
        confirmed_tracks = []
        lost_confirmed_tracks = []
        for track_id, bbox in zip(byte_track_ids, byte_track_bboxes):
            if track_id not in self.known_track_ids:
                new_tracks.append((track_id, bbox))
                self.known_track_ids.add(track_id)
            elif track_id in self.t_storage.unmatched:
                if self.t_storage.unmatched[track_id].should_reid(frame_id=frame_id):
                    unmatched_tracks.append((track_id, bbox))
            elif track_id in self.t_storage.unconfirmed:
                if self.t_storage.unconfirmed[track_id].should_reid(frame_id=frame_id):
                    unconfirmed_tracks.append((track_id, bbox))
            elif track_id in self.t_storage.confirmed:
                if self.t_storage.confirmed[track_id].should_reid(frame_id=frame_id):
                    confirmed_tracks.append((track_id, bbox))
            else:
                lost_confirmed_tracks.append((track_id, bbox))

        print(f"FRAME = {frame_id}, НОВЫХ = {len(new_tracks)}")

        if new_tracks:
            self.process_new_tracks(new_tracks=new_tracks, frame_id=frame_id, frame=frame)

        if unmatched_tracks:
            self.process_unmatched_tracklets(unmatched_tracks=unmatched_tracks, frame_id=frame_id, frame=frame)

        if unconfirmed_tracks:
            self.process_unconfirmed_tracklets(unconfirmed_tracks=unconfirmed_tracks, frame_id=frame_id, frame=frame)

        if confirmed_tracks:
            self.process_confirmed_tracklets(confirmed_tracks=confirmed_tracks, frame_id=frame_id, frame=frame)

        if lost_confirmed_tracks:
            self.process_lost_confirmed_tracklets(lost_confirmed_tracks, frame_id, frame)

    def process_new_tracks(self, new_tracks: list[tuple[int, tuple]], frame_id, frame):
        track_features = self.extract_features(
            tracks=new_tracks,
            frame=frame
        )

        new_tracklets: Dict[int, Tracklet] = {}
        for (track_id, bbox), feature in zip(new_tracks, track_features):
            tracklet = Tracklet(
                cam_id=self.cam_id,
                track_id=track_id,
                bbox=bbox,
                feature=feature
            )
            new_tracklets[track_id] = tracklet
            self.t_storage.add_tracklet(tracklet=tracklet)
            tracklet.mark_reid(frame_id=frame_id)

        self.matcher.matching_unmatched_tracklets(
            f_storage=self.f_storage,
            t_storage=self.t_storage
        )

    def process_unmatched_tracklets(self, unmatched_tracks, frame_id, frame):
        track_features = self.extract_features(
            tracks=unmatched_tracks,
            frame=frame
        )
        self.update_features(
            tracks=unmatched_tracks,
            tracklets=self.t_storage.unmatched,
            features=track_features,
            frame_id=frame_id
        )
        self.matcher.matching_unmatched_tracklets(
            f_storage=self.f_storage,
            t_storage=self.t_storage
        )

    def process_unconfirmed_tracklets(self, unconfirmed_tracks, frame_id, frame):
        track_features = self.extract_features(
            tracks=unconfirmed_tracks,
            frame=frame
        )
        self.update_features(
            tracks=unconfirmed_tracks,
            tracklets=self.t_storage.unconfirmed,
            features=track_features,
            frame_id=frame_id
        )
        self.matcher.matching_unconfirmed_tracklets(
            f_storage=self.f_storage,
            t_storage=self.t_storage
        )

    def process_confirmed_tracklets(self, confirmed_tracks, frame_id, frame):
        track_features = self.extract_features(
            tracks=confirmed_tracks,
            frame=frame
        )
        self.update_features(
            tracks=confirmed_tracks,
            tracklets=self.t_storage.confirmed,
            features=track_features,
            frame_id=frame_id
        )
        self.matcher.matching_confirmed_tracklets(
            f_storage=self.f_storage,
            t_storage=self.t_storage
        )

    def process_lost_confirmed_tracklets(self, lost_confirmed_tracks, frame_id, frame):
        # TODO
        pass

    def extract_features(self, tracks, frame):
        bboxes = [bbox for _, bbox in tracks]
        track_images = self.bboxes_to_images(frame, bboxes)
        return self.feats_manager.extract_features(track_images)

    @staticmethod
    def update_features(tracks, tracklets, features, frame_id):
        for (track_id, _), feature in zip(tracks, features):
            tracklets[track_id].update_feature(feature)
            tracklets[track_id].mark_reid(frame_id=frame_id)

    @staticmethod
    def bboxes_to_images(frame, bboxes):
        images = []
        for bbox in bboxes:
            x1, y1, x2, y2 = map(int, bbox)
            crop = frame[y1:y2, x1:x2]  # TODO обработка плохих
            images.append(crop)
        return images

    def update_searched_vehicle(self, searched_ids):
        # TODO
        searched_features_by_ids = self.car_feature_repository.get_features_by_car_ids(searched_ids)
        self.f_storage.searched = searched_features_by_ids
