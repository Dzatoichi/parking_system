from typing import Annotated
from functools import lru_cache

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.fcm_client import FCMClient
from src.db import get_session
from src.services.notification_service import NotificationService
from src.settings.config import settings


SessionDep = Annotated[AsyncSession, Depends(get_session)]


@lru_cache
def get_fcm_client() -> FCMClient:
    return FCMClient(
        project_id=settings.fcm_project_id,
        service_account_file=settings.fcm_service_account_file,
        timeout_seconds=settings.fcm_timeout_seconds,
    )


def get_notification_service(session: SessionDep) -> NotificationService:
    return NotificationService(session, fcm_client=get_fcm_client())


NotificationServiceDep = Annotated[NotificationService, Depends(get_notification_service)]
