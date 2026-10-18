"""Thread-safe registry for external vehicle-search requests.

The broker transport is deliberately kept separate. Incoming requests are expected
as dictionaries with event='vehicle_search_request', search_id and plates.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
import os
import threading
from typing import Callable, Iterable

try:
    from PlateOCRModule import normalize_plate_text
except Exception:  # Keep the integration contract importable during tooling/tests.
    def normalize_plate_text(value: str) -> str:
        return "".join(ch for ch in str(value).upper() if ch.isalnum())

MIN_PLATE_VOTES = 6  # strict votes > 5
MIN_AVERAGE_CONFIDENCE = 0.95  # strict confidence > 0.95


def _plate(value: object) -> str:
    raw = str(value or "").strip()
    normalized = normalize_plate_text(raw)
    return str(normalized or "").strip().upper()


class SearchRegistry:
    """Idempotent, thread-safe request registry supporting concurrent search IDs."""
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._requests: dict[str, set[str]] = {}
        self._found: set[tuple[str, str]] = set()
        self._decisions: dict[int, tuple[str, str]] = {}
        self._event_sink: Callable[[dict], None] | None = None

    def set_event_sink(self, sink: Callable[[dict], None] | None) -> None:
        with self._lock:
            self._event_sink = sink

    def add_request(self, payload: dict) -> bool:
        if not isinstance(payload, dict):
            raise ValueError("search request must be an object")
        search_id = str(payload.get("search_id", "")).strip()
        plates = payload.get("plates", payload.get("license_plates", []))
        if not search_id:
            raise ValueError("search_id is required")
        if isinstance(plates, str) or not isinstance(plates, Iterable):
            raise ValueError("plates must be a list of plate strings")
        normalized = {_plate(p) for p in plates}
        normalized.discard("")
        if not normalized:
            raise ValueError("at least one valid plate is required")
        with self._lock:
            # Re-delivery of an identical search_id is idempotent. A repeated ID
            # with changed plates updates that request without duplicating it.
            self._requests[search_id] = normalized
        return True

    def remove_request(self, search_id: str) -> None:
        with self._lock:
            self._requests.pop(str(search_id), None)

    def active_request_snapshot(self) -> dict[str, list[str]]:
        with self._lock:
            return {key: sorted(value) for key, value in self._requests.items() if value}

    def has_active_searches(self) -> bool:
        with self._lock:
            return any(self._requests.values())

    def decide_plate(self, journey_id: int, plate: str, votes: int, average_confidence: float) -> str:
        """Return PENDING, MATCH or REJECT only after both strict OCR thresholds pass."""
        if int(votes) <= 5 or float(average_confidence) <= MIN_AVERAGE_CONFIDENCE:
            return "PENDING"
        normalized = _plate(plate)
        with self._lock:
            previous = self._decisions.get(int(journey_id))
            if previous is not None:
                return previous[0]
            active = set().union(*self._requests.values()) if self._requests else set()
            decision = "MATCH" if normalized and normalized in active else "REJECT"
            self._decisions[int(journey_id)] = (decision, normalized)
            return decision

    def notify_found(self, *, journey_id: int, plate: str, camera_id: int,
                     zone: str, local_track_id: int | None = None) -> list[dict]:
        normalized = _plate(plate)
        emitted = []
        with self._lock:
            sink = self._event_sink
            for search_id, plates in self._requests.items():
                key = (search_id, normalized)
                if normalized not in plates or key in self._found:
                    continue
                event = {
                    "event": "vehicle_found", "schema_version": 1,
                    "search_id": search_id, "plate": normalized,
                    "journey_id": int(journey_id), "camera_id": int(camera_id),
                    "zone": str(zone).upper(), "local_track_id": local_track_id,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                self._found.add(key)
                plates.discard(normalized)
                emitted.append(event)
        # Never call external broker code while holding the registry lock.
        if sink is not None:
            for event in emitted:
                sink(event)
        return emitted

    def reset_journey(self, journey_id: int) -> None:
        with self._lock:
            self._decisions.pop(int(journey_id), None)


_REGISTRY = SearchRegistry()

def get_registry() -> SearchRegistry:
    return _REGISTRY

def integration_enabled() -> bool:
    return os.getenv("PARKING_INTEGRATION_MODE", "0").strip().lower() in {"1", "true", "yes", "on"}
