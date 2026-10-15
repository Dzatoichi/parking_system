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

    def test_matches_only_after_minimum_tracklet_samples(self):
        self.reid.add_identity_gallery(7, {"original": [np.array([1.0, 0.0])]})
        self.reid.track_features[(4, 12)] = [np.array([1.0, 0.0])]
        self.assertIsNone(self.reid.match_track_to_journey(4, 12, 7))
        self.reid.track_features[(4, 12)].append(np.array([0.99, 0.01]))
        self.assertGreaterEqual(self.reid.match_track_to_journey(4, 12, 7), 0.92)

    def test_rejects_dissimilar_appearance(self):
        self.reid.add_identity_gallery(7, {"original": [np.array([1.0, 0.0])]})
        self.reid.track_features[(4, 12)] = [
            np.array([0.0, 1.0]),
            np.array([0.0, 1.0]),
        ]
        self.assertIsNone(self.reid.match_track_to_journey(4, 12, 7))

    def test_ignores_invalid_embedding(self):
        self.assertIsNone(RuntimeReID._valid(np.array([0.0, 0.0])))
        self.assertIsNone(RuntimeReID._valid(np.array([np.nan, 1.0])))


if __name__ == "__main__":
    unittest.main()
