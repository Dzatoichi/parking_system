import unittest

import numpy as np

from RuntimeReID import RuntimeReID


class DummyFeatureManager:
    def extract_features(self, images):
        return [np.asarray([1.0, 0.0], dtype=np.float32) for _ in images]


class RuntimeReIDTests(unittest.TestCase):
    def setUp(self):
        self.reid = RuntimeReID(
            DummyFeatureManager(), threshold=0.92, sample_every=1, min_samples=2
        )

    def test_current_frame_embedding_is_enough_for_a_threshold_match(self):
        self.reid.add_identity_gallery(7, {"original": [np.array([1.0, 0.0])]})
        self.reid.last_query_features[(4, 12)] = np.array([1.0, 0.0])
        self.assertAlmostEqual(self.reid.match_track_to_journey(4, 12, 7), 1.0)

    def test_rejects_dissimilar_appearance(self):
        self.reid.add_identity_gallery(7, {"original": [np.array([1.0, 0.0])]})
        self.reid.track_features[(4, 12)] = [
            np.array([0.0, 1.0]),
            np.array([0.0, 1.0]),
        ]
        self.assertIsNone(self.reid.match_track_to_journey(4, 12, 7))

    def test_best_similarity_controls_acceptance(self):
        self.reid.add_identity_gallery(7, {
            "original": [
                np.array([1.0, 0.0]),
                np.array([0.8, 0.6]),
                np.array([0.8, 0.6]),
                np.array([0.8, 0.6]),
                np.array([0.8, 0.6]),
            ]
        })
        self.reid.track_features[(4, 12)] = [
            np.array([1.0, 0.0]),
            np.array([1.0, 0.0]),
        ]

        # The best pair scores 1.0 and is accepted; lower-scoring gallery views
        # do not dilute the score because top-k aggregation is not used.
        self.assertAlmostEqual(self.reid.match_track_to_journey(4, 12, 7), 1.0)
        self.assertAlmostEqual(self.reid.last_scores[(4, 12)][1], 1.0, places=5)

    def test_current_frame_compares_against_all_gallery_views(self):
        # The current frame can match a non-first gallery view; no averaging is used.
        self.reid.add_identity_gallery(7, {
            "original": [np.array([0.0, 1.0]), np.array([1.0, 0.0])]
        })
        self.reid.last_query_features[(4, 12)] = np.array([1.0, 0.0])

        score = self.reid.match_track_to_journey(4, 12, 7)

        self.assertAlmostEqual(score, 1.0)
        self.assertAlmostEqual(self.reid.last_scores[(4, 12)][1], 1.0, places=5)

    def test_diagnostic_matches_expire_after_their_frame_age(self):
        self.reid.add_identity_gallery(7, {"original": [np.array([1.0, 0.0])]})
        self.reid.log_feature_against_all_identities(
            4, 12, np.array([1.0, 0.0]), {7: "TEST"}, frame_id=20
        )
        self.assertIsNotNone(
            self.reid.get_fresh_diagnostic_match(4, 12, frame_id=22, max_age_frames=2)
        )
        self.assertIsNone(
            self.reid.get_fresh_diagnostic_match(4, 12, frame_id=23, max_age_frames=2)
        )
        self.assertNotIn((4, 12), self.reid.last_diagnostic_matches)

    def test_diagnostic_only_compares_journeys_in_active_search_tasks(self):
        self.reid.add_identity_gallery(7, {"original": [np.array([1.0, 0.0])]})
        self.reid.add_identity_gallery(8, {"original": [np.array([0.0, 1.0])]})
        self.reid.log_feature_against_all_identities(
            9, 3, np.array([0.0, 1.0]), {7: "PLATE-A", 8: "PLATE-B"},
            frame_id=30, journey_ids={7},
        )
        score, journey_id, plate = self.reid.last_diagnostic_matches[(9, 3)]
        self.assertEqual(journey_id, 7)
        self.assertEqual(plate, "PLATE-A")
        self.assertAlmostEqual(score, 0.0)

    def test_adaptive_sampling_rejects_duplicate_for_storage_but_keeps_current_query(self):
        frame = np.zeros((100, 100, 3), dtype=np.uint8)
        track = [(12, [10, 10, 80, 80])]
        self.reid.update_camera(4, 0, frame, track)
        self.reid.update_camera(4, 1, frame, track)
        self.assertEqual(len(self.reid.track_features[(4, 12)]), 1)
        # Matching still sees this frame even though its vector was not stored twice.
        np.testing.assert_allclose(
            self.reid.last_query_features[(4, 12)], np.array([1.0, 0.0], dtype=np.float32)
        )

    def test_ignores_invalid_embedding(self):
        self.assertIsNone(RuntimeReID._valid(np.array([0.0, 0.0])))
        self.assertIsNone(RuntimeReID._valid(np.array([np.nan, 1.0])))


if __name__ == "__main__":
    unittest.main()
