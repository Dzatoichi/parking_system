import enum

"""
FREE: свободное место,
OCCUPIED: занятое место,
RESERVED: зарезервированное место.
"""
class SpotStatus(enum.Enum):
    FREE = "free"
    OCCUPIED = "occupied"
    RESERVED = "reserved"
