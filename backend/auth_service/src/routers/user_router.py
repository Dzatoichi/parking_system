from pydantic import BaseModel, EmailStr, Field
from fastapi import APIRouter, Body, Depends, HTTPException, status

from src.models.users import User
from src.schemas.enums import UserRole
from src.schemas.user_schemas import (
    RefreshTokenRequestSchema,
    UserLoginSchema,
    UserPasswordUpdateSchema,
    UserReadSchema,
    UserRegisterSchema,
    UserUpdateMeSchema,
)
from src.services.auth_service import AuthService
from src.utils.dependencies import get_auth_service, get_current_user, require_roles

user_router = APIRouter(prefix="/users", tags=["users"])


class MobileRegistrationSchema(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    last_name: str = Field(min_length=1, max_length=128)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


ROLE_TO_MOBILE_ID: dict[UserRole, int] = {
    UserRole.TENANT: 1,
    UserRole.LANDLORD: 2,
    UserRole.OPERATOR: 3,
    UserRole.ADMIN: 4,
}


def _split_full_name(full_name: str | None) -> tuple[str | None, str | None]:
    if not full_name:
        return None, None
    parts = full_name.split(maxsplit=1)
    if len(parts) == 1:
        return parts[0], None
    return parts[1], parts[0]


def _to_mobile_user(user: User) -> dict:
    name, last_name = _split_full_name(user.full_name)
    return {
        "id": user.id,
        "role": ROLE_TO_MOBILE_ID.get(user.role, 1),
        "name": name,
        "last_name": last_name,
        "email": user.email,
    }


def _to_mobile_auth_response(result: dict) -> dict:
    tokens = result["tokens"]
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "user": _to_mobile_user(result["user"]),
    }


@user_router.post("/auth")
async def mobile_login(
    data: UserLoginSchema,
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    result = await auth_service.login_user(data)
    return _to_mobile_auth_response(result)


@user_router.post("/register")
async def mobile_register(
    data: MobileRegistrationSchema,
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    result = await auth_service.register_user(
        UserRegisterSchema(
            email=data.email,
            password=data.password,
            confirm_password=data.password,
            full_name=f"{data.last_name} {data.name}",
            role=UserRole.TENANT,
        )
    )
    return {"id": result["user"].id, "detail": None}


@user_router.post("/activate/")
async def mobile_activate(id: int, code: str) -> dict:
    return {"id": id, "detail": None}


@user_router.post("/refresh")
async def mobile_refresh(
    data: RefreshTokenRequestSchema | None = Body(default=None),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    if data is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="refresh_token is required",
        )
    return await auth_service.refresh_tokens(data.refresh_token)


@user_router.get("/me", response_model=UserReadSchema)
async def get_me(current_user: User = Depends(get_current_user)) -> UserReadSchema:
    return UserReadSchema.model_validate(current_user)


@user_router.patch("/me", response_model=UserReadSchema)
async def update_me(
    data: UserUpdateMeSchema,
    auth_service: AuthService = Depends(get_auth_service),
    current_user: User = Depends(get_current_user),
) -> UserReadSchema:
    user = await auth_service.update_me(current_user.id, data)
    return UserReadSchema.model_validate(user)


@user_router.post("/me/change-password")
async def change_password(
    data: UserPasswordUpdateSchema,
    auth_service: AuthService = Depends(get_auth_service),
    current_user: User = Depends(get_current_user),
) -> dict[str, str]:
    return await auth_service.change_password(current_user.id, data)


@user_router.get("", response_model=list[UserReadSchema])
async def list_users(
    auth_service: AuthService = Depends(get_auth_service),
    _: User = Depends(require_roles(UserRole.ADMIN, UserRole.OPERATOR)),
) -> list[UserReadSchema]:
    users = await auth_service.list_users()
    return [UserReadSchema.model_validate(user) for user in users]


@user_router.get("/{user_id}", response_model=UserReadSchema)
async def get_user_by_id(
    user_id: int,
    auth_service: AuthService = Depends(get_auth_service),
) -> UserReadSchema:
    user = await auth_service.get_user_by_id(user_id)
    return UserReadSchema.model_validate(user)
