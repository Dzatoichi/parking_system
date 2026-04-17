from src.dao.userDAO import UserDAO

from src.core.security.hash_helper import hash_helper
from src.dao.permssionDAO import PermissionDAO
from src.schemas.user_schemas import UserReadSchema


class AuthService:
    def __init__(
        self,
        db_helper,
        user_repo: UserDAO,
        permission_repo: PermissionDAO,
    ):
        self.db_helper = db_helper
        self.user_repo = user_repo
        self.permission_repo = permission_repo

    def register_user(
            self,
            user: UserReadSchema,
            data: UserReadSchema,
    ) -> UserReadSchema:
        pass