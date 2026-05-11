# clients/auth_client.py
import httpx
from typing import Optional
from fastapi import HTTPException, status


class AuthServiceClient:
    def __init__(self, base_url: str = "http://auth-service:8003"):
        self.base_url = base_url

    async def get_current_user(self, token: str) -> Optional[dict]:
        """
        Получение текущего пользователя через эндпоинт /users/me
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/users/me",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=3.0
                )

                if response.status_code == 200:
                    user_data = response.json()
                    return {
                        "id": user_data["id"],
                        "email": user_data["email"],
                        "full_name": user_data.get("full_name"),
                        "role": user_data["role"],
                        "is_active": user_data["is_active"]
                    }
                elif response.status_code == 401:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid or expired token"
                    )
                else:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Auth service error: {response.text}"
                    )

            except httpx.TimeoutException:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Auth service timeout"
                )
            except httpx.RequestError as e:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Auth service unavailable: {str(e)}"
                )

    async def get_user_by_id(self, user_id: int, token: str) -> Optional[dict]:
        """
        Получение пользователя по ID (для администраторов)
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/users/{user_id}",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=3.0
                )

                if response.status_code == 200:
                    return response.json()
                return None

            except Exception:
                return None