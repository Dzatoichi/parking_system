from fastapi import APIRouter, Depends

from src.models.users import User
from src.schemas.enums import UserRole
from src.schemas.user_schemas import UserPasswordUpdateSchema, UserReadSchema, UserUpdateMeSchema
from src.services.auth_service import AuthService
from src.utils.dependencies import get_auth_service, get_current_user, require_roles

user_router = APIRouter(prefix="/users", tags=["users"])


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
