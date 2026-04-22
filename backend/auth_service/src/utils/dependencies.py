from fastapi import Depends
from src.dao.userDAO import UserDAO
from src.dao.permissionDAO import PermissionDAO

from src.services.user_service import AuthService

from src.database.base import db_helper


def get_user_dao():
    return UserDAO()

def get_permission_dao():
    return PermissionDAO()


def get_auth_service(
        user_repo: UserDAO = Depends(get_user_dao),
        perm_repo: PermissionDAO = Depends(get_permission_dao),
) -> AuthService:
    from src.services.auth_service import AuthService

    return AuthService(
        db_helper=db_helper,
        user_repo=user_repo,
        permission_repo=perm_repo,
    )
