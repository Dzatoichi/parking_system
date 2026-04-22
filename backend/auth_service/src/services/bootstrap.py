from src.database.base import async_session_maker
from src.services.auth_service import AuthService
from src.settings.config import settings


async def bootstrap_defaults() -> None:
    async with async_session_maker() as session:
        auth_service = AuthService(session)
        await auth_service.ensure_permissions_seeded()
        if settings.BOOTSTRAP_ADMIN_ENABLED:
            await auth_service.create_bootstrap_admin(
                email=settings.BOOTSTRAP_ADMIN_EMAIL,
                password=settings.BOOTSTRAP_ADMIN_PASSWORD,
                full_name=settings.BOOTSTRAP_ADMIN_FULL_NAME,
            )
        await session.commit()
