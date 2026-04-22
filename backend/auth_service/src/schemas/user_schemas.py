from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator, model_validator

from src.schemas.enums import UserRole


PasswordStr = Annotated[str, StringConstraints(min_length=8, max_length=128)]


class UserBaseSchema(BaseModel):
    email: EmailStr
    full_name: str | None = Field(default=None, max_length=255)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return value.lower()

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class UserReadSchema(UserBaseSchema):
    id: int
    role: UserRole
    is_active: bool
    created_at: datetime


class UserRegisterSchema(UserBaseSchema):
    password: PasswordStr
    confirm_password: PasswordStr
    role: UserRole = UserRole.TENANT
    register_token: Annotated[str | None, StringConstraints(min_length=8, max_length=1024)] = None

    @model_validator(mode="after")
    def check_passwords_match(self) -> "UserRegisterSchema":
        if self.password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class UserLoginSchema(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return value.lower()

    model_config = ConfigDict(str_strip_whitespace=True)


class UserUpdateMeSchema(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)

    model_config = ConfigDict(str_strip_whitespace=True)


class UserPasswordUpdateSchema(BaseModel):
    current_password: PasswordStr
    new_password: PasswordStr
    confirm_password: PasswordStr

    @model_validator(mode="after")
    def check_passwords_match(self) -> "UserPasswordUpdateSchema":
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class UserForgotPasswordSchema(BaseModel):
    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return value.lower()


class PasswordResetConfirmSchema(BaseModel):
    token: Annotated[str, StringConstraints(min_length=16, max_length=256)]
    new_password: PasswordStr
    confirm_new_password: PasswordStr

    @model_validator(mode="after")
    def check_passwords_match(self) -> "PasswordResetConfirmSchema":
        if self.new_password != self.confirm_new_password:
            raise ValueError("Passwords do not match")
        return self


class RefreshTokenRequestSchema(BaseModel):
    refresh_token: Annotated[str, StringConstraints(min_length=16, max_length=4096)]


class AuthTokensSchema(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AuthResponseSchema(BaseModel):
    user: UserReadSchema
    tokens: AuthTokensSchema


class ForgotPasswordResponseSchema(BaseModel):
    message: str
    reset_token: str | None = None


class InvitationCreateSchema(BaseModel):
    email: EmailStr
    role: UserRole
    full_name: str | None = Field(default=None, max_length=255)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: EmailStr) -> str:
        return value.lower()

    @model_validator(mode="after")
    def validate_role(self) -> "InvitationCreateSchema":
        if self.role not in {UserRole.OPERATOR, UserRole.ADMIN}:
            raise ValueError("Invitation flow is reserved for operator or admin accounts")
        return self


class InvitationReadSchema(BaseModel):
    email: EmailStr
    role: UserRole
    register_token: str


class PermissionReadSchema(BaseModel):
    id: int
    code_name: str
    description: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UserWithPermissionsSchema(UserReadSchema):
    permissions: list[PermissionReadSchema] = Field(default_factory=list)
