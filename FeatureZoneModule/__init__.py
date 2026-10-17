"""Zone-based Re-ID feature collection.

The session coordinator has no computer-vision dependencies. Keep its import
lightweight; load the OpenCV-backed gallery manager only when requested.
"""
from .EntrySessionManager import EntrySessionManager, EntrySession

__all__ = ["FeatureZoneManager", "TrackGallery", "EntrySessionManager", "EntrySession"]


def __getattr__(name: str):
    if name in {"FeatureZoneManager", "TrackGallery"}:
        from .FeatureZoneManager import FeatureZoneManager, TrackGallery

        globals().update(
            FeatureZoneManager=FeatureZoneManager,
            TrackGallery=TrackGallery,
        )
        return globals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
