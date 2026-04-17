from fastapi import APIRouter
from fastapi.params import Depends

from src.schemas.user_schemas import UserReadSchema

from src.schemas.user_schemas import UserRegisterSchema
from src.services.user_service import AuthService
from src.utils.dependencies import get_auth_service

auth_router = APIRouter(prefix="/auth", tags=["Authorization"])

@auth_router.post("/register", response_model=UserReadSchema, status_code=201)
async def register_user(
        data: UserRegisterSchema,
        auth_service: AuthService = Depends(get_auth_service),
) -> UserReadSchema:
    user = await auth_service.register_user(data)
    return user

