import logging
from typing import Dict

import numpy as np
from FeaturesModule.FeaturesManager import FeaturesManager
from TrackletModule.FindStorage import FindStorage
from TrackletModule.Tracklet import Tracklet
from TrackletModule.TrackletStorage import TrackletStorage

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Matcher:
    def __init__(self, features_manager: FeaturesManager, similarity_threshold: float = 0.7,
                 frames_for_confirm: int = 3, frames_for_lost: int = 5):
        self.features_manager: FeaturesManager = features_manager
        self.similarity_threshold: float = similarity_threshold
        self.frames_for_confirm: int = frames_for_confirm
        self.frames_for_lost: int = frames_for_lost

    def matching_unmatched_tracklets(self, f_storage: FindStorage,
                                     t_storage: TrackletStorage) -> None:

        print("-" * 30, "UNMATCHED ", "-" * 30)

        result_pairs = self._match(
            vehicles=f_storage.searched,
            tracklets=t_storage.unmatched
        )

        for vehicle_id, tracklet in result_pairs:
            print("ДЕЛАЕМ ТРЕКЛЕТ UNCONFIRMED")
            t_storage.unmatched_2_unconfirmed(vehicle_id=vehicle_id, tracklet=tracklet)

    def matching_unconfirmed_tracklets(self, f_storage: FindStorage,
                                       t_storage: TrackletStorage) -> None:

        print("-" * 30, "UNCONFIRMED ", "-" * 30)

        result_pairs = self._match(
            vehicles=f_storage.searched,
            tracklets=t_storage.unconfirmed
        )

        for vehicle_id, tracklet in result_pairs:
            if vehicle_id in tracklet.match_count_by_vehicle_id:
                tracklet.match_count_by_vehicle_id[vehicle_id] += 1
                if tracklet.match_count_by_vehicle_id[vehicle_id] >= self.frames_for_confirm:
                    print(
                        f"!!!!!!!!!!!!!!!!!! CONFIRMED !!!!!!!!!!!!!!  veh_{vehicle_id}, track_{tracklet.current_track_id}")
                    t_storage.unconfirmed_2_confirmed(tracklet=tracklet, vehicle_id=vehicle_id)
                    f_storage.vehicle_found(vehicle_id=vehicle_id)
            else:
                tracklet.match_count_by_vehicle_id[vehicle_id] = 1

    def matching_confirmed_tracklets(self, f_storage: FindStorage,
                                     t_storage: TrackletStorage) -> None:

        print("-" * 30, "CONFIRMED ", "-" * 30)

        result_pairs = self._match(
            vehicles=f_storage.found,
            tracklets=t_storage.confirmed
        )

        result_pairs_dict = {
            vehicle_id: tracklet
            for vehicle_id, tracklet in result_pairs
        }

        for _, tracklet in t_storage.confirmed.items():
            vehicle_id = tracklet.vehicle_id
            if vehicle_id not in result_pairs_dict:
                tracklet.lost_counter += 1
                print(f"!!!!!!!!!!!!!!!!!! LOST !!!!!!!!!!!!!!  veh_{vehicle_id}, track_{tracklet.current_track_id}")
                if tracklet.lost_counter >= self.frames_for_lost:
                    print(
                        f"!!!!!!!!!!!!!!!!!! LOST !!!!!!!!!!!!!!  veh_{vehicle_id}, track_{tracklet.current_track_id}")
                    t_storage.confirmed_2_unconfirmed(tracklet=tracklet)
                    f_storage.vehicle_lost(vehicle_id=vehicle_id)
            else:
                tracklet.lost_counter = max(0, tracklet.lost_counter - 1)

    def _match(self, vehicles: Dict[int, list[np.ndarray]],
               tracklets: Dict[int, Tracklet]) -> list[tuple[int, Tracklet]]:

        print("СТАТИСТИКА МЭТЧЕРА")
        candidates = []
        for vehicle_id, vehicle_features in vehicles.items():
            for _, tracklet in tracklets.items():
                similarities = [
                    self.features_manager.calculate_similarity(tracklet.mean_feature, vehicle_feature)
                    for vehicle_feature in vehicle_features
                ]
                # similarities = self.clip_features_manager.calc_similarity(track_mean_feature=tracklet.mean_feature,
                #                                                           vehicle_features=vehicle_features)

                similarities.sort(reverse=True)

                avg_sim = sum(similarities[:5]) / 5
                # avg_sim = np.percentile(similarities, 85)

                print(vehicle_id, tracklet.current_track_id, avg_sim)

                if avg_sim >= self.similarity_threshold:
                    candidates.append((vehicle_id, tracklet, avg_sim))

                    print(f"veh_{vehicle_id} - track_{tracklet.current_track_id} - {avg_sim}")

        candidates.sort(key=lambda x: x[2], reverse=True)

        print("=" * 60)
        print("ВЫВОД МЭТЧЕРА")

        used_vehicle_ids = set()
        used_tracklet_ids = set()
        pairs = []
        for vehicle_id, tracklet, similarity in candidates:
            if vehicle_id in used_vehicle_ids:
                continue
            if tracklet.tracklet_id in used_tracklet_ids:
                continue

            pairs.append((vehicle_id, tracklet))
            used_vehicle_ids.add(vehicle_id)
            used_tracklet_ids.add(tracklet.tracklet_id)

            print(vehicle_id, tracklet.current_track_id)
        print("-" * 60)

        return pairs
