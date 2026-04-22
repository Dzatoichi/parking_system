from enum import Enum


class UserRole(Enum):
    LANDLORD = "landlord"
    TENANT = "tenant"
    OPERATOR = "operator"
    admin = "admin"
