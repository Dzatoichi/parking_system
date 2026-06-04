import enum

class EventType(enum.Enum):
    SPOT_STATUS_CHANGED = "spot_status_changed"

    BOOKING_CREATES = "booking_created"
    BOOKING_CANCELED = "booking_canceled"
    BOOKING_COMPLETED = "booking_completed"
    BOOKING_CONFLICT = "booking_conflict"

    BARRIER_OPENED = "barrier_opened"
    BARRIER_CLOSED = "barrier_closed"
    LIGHTING_CHANGED = "lighting_changed"
    DEVICE_UNAVAILABLE = "device_unavailable"

    VEHICLE_DETECTED = "vehicle_detected"
    VEHICLE_DEPARTED ="vehicle_departed"
    