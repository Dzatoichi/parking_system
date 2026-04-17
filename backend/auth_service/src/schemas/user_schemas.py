import builtins
from typing import Annotated

from pydantic import BaseModel, EmailStr, field_validator, ConfigDict, StringConstraints, model_validator
from datetime import datetime

from src.schemas.enums import UserRole


class UserBaseSchema(BaseModel):
    """
    Базовая схема пользователя.
    """

    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: EmailStr) -> str:
        return v.lower()

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class UserLoginSchema(BaseModel):
    """
    Схема аутентификации пользователя.
    """

    email: EmailStr
    password: str

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class UserRegisterSchema(UserLoginSchema):
    """
    Схема регистрации пользователя.
    """

    confirm_password: str
    register_token: Annotated[str, StringConstraints(min_length=8, max_length=512)] | None = None

    @model_validator(mode="after")
    def check_passwords_match(self) -> "UserRegisterSchema":
        """
        Метод проверки на совпадение пароля.
        """
        if self.password != self.confirm_password:
            raise ValueError("Пароль не совпадает")
        return self


class UserUpdateSchema(UserBaseSchema):
    """
    Схема изменения пользователя.
    """

    pass


class UserUpdateMeSchema(UserBaseSchema):
    """
    Схема для изменения собственных данных пользователя
    """

    pass


class UserReadSchema(UserBaseSchema):
    """
    Схема получения пользователя.
    """

    id: int
    role: UserRole
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class UserAuthRequestSchema(BaseModel):
    """
    Схема для принятия авторизационного запроса(токена).
    """

    access_token: Annotated[builtins.str, StringConstraints(min_length=8, max_length=4096)]

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


class PasswordResetConfirmSchema(BaseModel):
    """
    Схема подтверждения сброса пароля пользователя.
    """

    token: str
    new_password: str
    confirm_new_password: str

    @model_validator(mode="after")
    def check_passwords_match(self) -> "PasswordResetConfirmSchema":
        if self.new_password != self.confirm_new_password:
            raise ValueError("Passwords do not match")
        return self


class UserPasswordUpdateSchema(BaseModel):
    """
    Схема изменения пароля пользователя.
    """

    current_password: str
    new_password: str
    confirm_password: str

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)

    @model_validator(mode="after")
    def check_passwords_match(self) -> "UserPasswordUpdateSchema":
        if self.new_password != self.confirm_password:
            raise ValueError("Passwords do not match")
        return self


class UserForgotPasswordSchema(BaseModel):
    """
    Схема запроса на изменение пароля в случае, если пользователь забыл пароль.
    """

    email: EmailStr

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: EmailStr) -> str:
        return v.lower()

    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)
