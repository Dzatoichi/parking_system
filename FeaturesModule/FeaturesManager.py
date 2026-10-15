import numpy as np
from torch.cuda import is_available
from torchreid.utils import FeatureExtractor


class FeaturesManager:
    """OSNet-AIN embedding extractor with explicit finite, L2-normalized output."""

    def __init__(self, path_to_osnet_weights):
        self.extractor = FeatureExtractor(
            model_name="osnet_ain_x1_0",
            model_path=path_to_osnet_weights,
            device="cuda" if is_available() else "cpu",
        )

    def extract_features(self, image_list):
        """Extract a batch of vehicle crops and return one unit vector per crop."""
        if not image_list:
            return []

        tensor_features = self.extractor(image_list)
        if hasattr(tensor_features, "detach"):
            tensor_features = tensor_features.detach().cpu().numpy()

        matrix = np.asarray(tensor_features, dtype=np.float32)
        if matrix.ndim == 1:
            matrix = matrix.reshape(1, -1)
        if matrix.ndim != 2 or matrix.shape[0] != len(image_list):
            raise RuntimeError(
                f"OSNet вернул форму {matrix.shape} для {len(image_list)} кропов"
            )

        matrix = np.nan_to_num(matrix, copy=False, nan=0.0, posinf=0.0, neginf=0.0)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        matrix = np.divide(
            matrix,
            np.maximum(norms, 1e-12),
            out=np.zeros_like(matrix),
            where=norms > 1e-12,
        )
        return [row.copy() for row in matrix]

    @staticmethod
    def calculate_similarity(feature_vector_1, feature_vector_2):
        """Cosine similarity for single vectors; embeddings are normalized defensively."""
        first = np.asarray(feature_vector_1, dtype=np.float32).reshape(-1)
        second = np.asarray(feature_vector_2, dtype=np.float32).reshape(-1)
        if first.shape != second.shape or first.size == 0:
            return -1.0
        if not np.isfinite(first).all() or not np.isfinite(second).all():
            return -1.0
        norm_first = np.linalg.norm(first)
        norm_second = np.linalg.norm(second)
        if norm_first <= 1e-12 or norm_second <= 1e-12:
            return -1.0
        return float(np.dot(first, second) / (norm_first * norm_second))
