from fastapi import APIRouter, Depends, status

from src.models.users import User
from src.schemas.enums import UserRole
from src.schemas.user_schemas import (
    AuthResponseSchema,
    AuthTokensSchema,
    ForgotPasswordResponseSchema,
    InvitationCreateSchema,
    InvitationReadSchema,
    PasswordResetConfirmSchema,
    RefreshTokenRequestSchema,
    UserForgotPasswordSchema,
    UserLoginSchema,
    UserReadSchema,
    UserRegisterSchema,
)
from src.services.auth_service import AuthService
from src.utils.dependencies import get_auth_service, require_roles

auth_router = APIRouter(prefix="/auth", tags=["auth"])


@auth_router.post("/register", response_model=AuthResponseSchema, status_code=status.HTTP_201_CREATED)
async def register_user(
    data: UserRegisterSchema,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponseSchema:
    result = await auth_service.register_user(data)
    return AuthResponseSchema.model_validate(result)


@auth_router.post("/login", response_model=AuthResponseSchema)
async def login_user(
    data: UserLoginSchema,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponseSchema:
    result = await auth_service.login_user(data)
    return AuthResponseSchema.model_validate(result)


@auth_router.post("/refresh", response_model=AuthTokensSchema)
async def refresh_tokens(
    data: RefreshTokenRequestSchema,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthTokensSchema:
    result = await auth_service.refresh_tokens(data.refresh_token)
    return AuthTokensSchema.model_validate(result)


@auth_router.post("/logout")
async def logout(
    data: RefreshTokenRequestSchema,
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, str]:
    return await auth_service.logout(data.refresh_token)


@auth_router.post("/forgot-password", response_model=ForgotPasswordResponseSchema)
async def forgot_password(
    data: UserForgotPasswordSchema,
    auth_service: AuthService = Depends(get_auth_service),
) -> ForgotPasswordResponseSchema:
    result = await auth_service.forgot_password(data)
    return ForgotPasswordResponseSchema.model_validate(result)


@auth_router.post("/reset-password")
async def reset_password(
    data: PasswordResetConfirmSchema,
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, str]:
    return await auth_service.reset_password(data)


@auth_router.post("/invitations", response_model=InvitationReadSchema, status_code=status.HTTP_201_CREATED)
async def create_invitation(
    data: InvitationCreateSchema,
    auth_service: AuthService = Depends(get_auth_service),
    current_user: User = Depends(require_roles(UserRole.ADMIN)),
) -> InvitationReadSchema:
    result = await auth_service.create_invitation(current_user, data)
    return InvitationReadSchema.model_validate(result)
