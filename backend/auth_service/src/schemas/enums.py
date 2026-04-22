from enum import StrEnum


class UserRole(StrEnum):
    TENANT = "tenant"
    LANDLORD = "landlord"
    OPERATOR = "operator"
    ADMIN = "admin"


class TokenType(StrEnum):
    ACCESS = "access"
    REFRESH = "refresh"
    REGISTER = "register"
