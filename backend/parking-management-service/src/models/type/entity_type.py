import enum


class EntityType(enum.Enum):
    BOOKING = "booking"
    SPOT = "spot"
    BARRIER = "barrier"
    LIGHTNING = "lightning"
    VEHICLE = "vehicle"