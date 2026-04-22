from collections.abc import Sequence

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security.hash_helper import hash_helper
from src.dao.permissionDAO import PermissionDAO
from src.dao.tokensDAO import RefreshTokenDAO, StatefulTokenDAO
from src.dao.userDAO import UserDAO
from src.models.users import User
from src.schemas.enums import UserRole
from src.schemas.user_schemas import (
    InvitationCreateSchema,
    PasswordResetConfirmSchema,
    UserForgotPasswordSchema,
    UserLoginSchema,
    UserPasswordUpdateSchema,
    UserRegisterSchema,
    UserUpdateMeSchema,
)
from src.services.token_service import JWTTokensService, StatefulTokenService


ROLE_PERMISSIONS: dict[UserRole, list[str]] = {
    UserRole.TENANT: [
        "bookings:create",
        "bookings:read_own",
        "profile:update_own",
    ],
    UserRole.LANDLORD: [
        "spots:manage_own",
        "bookings:approve_own",
        "profile:update_own",
        "payments:read_own",
    ],
    UserRole.OPERATOR: [
        "parking:monitor",
        "bookings:read_all",
        "events:read_all",
    ],
    UserRole.ADMIN: [
        "users:manage",
        "invitations:create",
        "parking:monitor",
        "bookings:read_all",
    ],
}


ROLE_DESCRIPTIONS: dict[str, str] = {
    "bookings:create": "Create a booking request",
    "bookings:read_own": "Read own bookings",
    "profile:update_own": "Update own profile data",
    "spots:manage_own": "Manage owned parking spots",
    "bookings:approve_own": "Approve bookings for owned spots",
    "payments:read_own": "Read own revenue or payment status",
    "parking:monitor": "Monitor parking state in operator UI",
    "bookings:read_all": "Read all booking records",
    "events:read_all": "Read parking events and incidents",
    "users:manage": "Manage users and roles",
    "invitations:create": "Create invitation tokens for privileged users",
}


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_dao = UserDAO(session)
        self.permission_dao = PermissionDAO(session)
        self.refresh_token_dao = RefreshTokenDAO(session)
        self.stateful_token_dao = StatefulTokenDAO(session)
        self.jwt_tokens_service = JWTTokensService(self.refresh_token_dao)
        self.stateful_token_service = StatefulTokenService(self.stateful_token_dao)

    async def register_user(self, data: UserRegisterSchema) -> dict:
        existing_user = await self.user_dao.get_by_email(data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User with this email already exists",
            )

        role = data.role
        invited_full_name = data.full_name
        if data.register_token:
            invitation_payload = self.jwt_tokens_service.validate_register_token(data.register_token)
            if invitation_payload.get("email") != data.email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Registration token was issued for another email",
                )
            role = UserRole(invitation_payload["role"])
            invited_full_name = invited_full_name or invitation_payload.get("full_name")
        elif role not in {UserRole.TENANT, UserRole.LANDLORD}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registration token is required for privileged roles",
            )

        user = await self.user_dao.create_user(
            {
                "email": data.email,
                "full_name": invited_full_name,
                "hashed_password": hash_helper.hash(data.password),
                "role": role,
                "is_active": True,
            }
        )
        await self._assign_role_permissions(user.id, role)
        await self.session.commit()
        await self.session.refresh(user)

        auth_tokens = await self.jwt_tokens_service.create_auth_tokens(user_id=user.id, role=user.role)
        await self.session.commit()

        user = await self.user_dao.get_with_permissions(user.id)
        return {"user": user, "tokens": auth_tokens}

    async def login_user(self, data: UserLoginSchema) -> dict:
        user = await self.user_dao.get_by_email(data.email)
        if not user or not hash_helper.verify_password(data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive",
            )

        auth_tokens = await self.jwt_tokens_service.create_auth_tokens(user_id=user.id, role=user.role)
        await self.session.commit()
        user = await self.user_dao.get_with_permissions(user.id)
        return {"user": user, "tokens": auth_tokens}

    async def refresh_tokens(self, refresh_token: str) -> dict:
        payload = await self.jwt_tokens_service.validate_refresh_token(refresh_token)
        user = await self.get_user_by_id(int(payload["sub"]))
        await self.jwt_tokens_service.revoke_refresh_token(refresh_token)
        auth_tokens = await self.jwt_tokens_service.create_auth_tokens(user_id=user.id, role=user.role)
        await self.session.commit()
        return auth_tokens

    async def logout(self, refresh_token: str) -> dict[str, str]:
        await self.jwt_tokens_service.revoke_refresh_token(refresh_token)
        await self.session.commit()
        return {"message": "Session finished successfully"}

    async def forgot_password(self, data: UserForgotPasswordSchema) -> dict[str, str | None]:
        user = await self.user_dao.get_by_email(data.email)
        if not user:
            return {"message": "If the user exists, a reset token has been generated", "reset_token": None}

        reset_token = await self.stateful_token_service.create_reset_token(user.id)
        await self.session.commit()
        return {
            "message": "Reset token generated. In MVP it is returned directly for demo/testing.",
            "reset_token": reset_token.token,
        }

    async def reset_password(self, data: PasswordResetConfirmSchema) -> dict[str, str]:
        reset_token = await self.stateful_token_service.validate_reset_token(data.token)
        user = await self.get_user_by_id(reset_token.user_id)
        user.hashed_password = hash_helper.hash(data.new_password)
        await self.stateful_token_service.mark_token_as_used(reset_token.id)
        await self.session.commit()
        return {"message": "Password updated successfully"}

    async def get_current_user(self, access_token: str) -> User:
        payload = self.jwt_tokens_service.validate_access_token(access_token)
        return await self.get_user_by_id(int(payload["sub"]))

    async def update_me(self, user_id: int, data: UserUpdateMeSchema) -> User:
        user = await self.get_user_by_id(user_id)
        if data.full_name is not None:
            user.full_name = data.full_name
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def change_password(self, user_id: int, data: UserPasswordUpdateSchema) -> dict[str, str]:
        user = await self.get_user_by_id(user_id)
        if not hash_helper.verify_password(data.current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Current password is invalid",
            )

        user.hashed_password = hash_helper.hash(data.new_password)
        await self.session.commit()
        return {"message": "Password updated successfully"}

    async def create_invitation(self, current_user: User, data: InvitationCreateSchema) -> dict:
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only admin can create privileged invitations",
            )

        token = self.jwt_tokens_service.create_register_token(
            email=data.email,
            role=data.role,
            full_name=data.full_name,
        )
        return {
            "email": data.email,
            "role": data.role,
            "register_token": token,
        }

    async def list_users(self) -> Sequence[User]:
        return await self.user_dao.list_all()

    async def get_user_by_id(self, user_id: int) -> User:
        user = await self.user_dao.get_with_permissions(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return user

    async def ensure_permissions_seeded(self) -> None:
        for code_name, description in ROLE_DESCRIPTIONS.items():
            await self.permission_dao.create_if_missing(code_name, description)
        await self.session.flush()

    async def create_bootstrap_admin(self, email: str, password: str, full_name: str | None) -> None:
        existing_user = await self.user_dao.get_by_email(email)
        if existing_user:
            return

        user = await self.user_dao.create_user(
            {
                "email": email,
                "full_name": full_name,
                "hashed_password": hash_helper.hash(password),
                "role": UserRole.ADMIN,
                "is_active": True,
            }
        )
        await self._assign_role_permissions(user.id, UserRole.ADMIN)

    async def _assign_role_permissions(self, user_id: int, role: UserRole) -> None:
        permissions = await self.permission_dao.get_by_codes(ROLE_PERMISSIONS[role])
        permission_ids = [permission.id for permission in permissions]
        await self.user_dao.replace_permissions(user_id, permission_ids)
