from fastapi import APIRouter, Query, status

from src.schemas import (
    NotificationCreate,
    NotificationRead,
    PaginatedNotifications,
    TemplateEvent,
    TokenRead,
    TokenRegister,
)
from src.utils.dependencies import NotificationServiceDep


notification_router = APIRouter(tags=["notifications"])


@notification_router.post("/devices/register", response_model=TokenRead, status_code=status.HTTP_201_CREATED)
async def register_device(body: TokenRegister, service: NotificationServiceDep) -> TokenRead:
    return await service.register_token(body)


@notification_router.post("/devices/unregister", response_model=TokenRead)
async def unregister_device(token: str, service: NotificationServiceDep) -> TokenRead:
    return await service.unregister_token(token)


@notification_router.get("/devices/user/{user_id}", response_model=list[TokenRead])
async def list_user_devices(user_id: int, service: NotificationServiceDep) -> list[TokenRead]:
    return await service.list_user_tokens(user_id)


@notification_router.post("/notifications", response_model=NotificationRead, status_code=status.HTTP_201_CREATED)
async def send_notification(body: NotificationCreate, service: NotificationServiceDep) -> NotificationRead:
    return await service.send_notification(body)


@notification_router.post("/notifications/from-event", response_model=NotificationRead, status_code=status.HTTP_201_CREATED)
async def send_from_event(body: TemplateEvent, service: NotificationServiceDep) -> NotificationRead:
    return await service.send_from_event(body)


@notification_router.post("/notifications/test", response_model=NotificationRead, status_code=status.HTTP_201_CREATED)
async def send_test_notification(user_id: int, service: NotificationServiceDep) -> NotificationRead:
    return await service.send_notification(
        NotificationCreate(
            user_id=user_id,
            type="test",
            title="Test notification",
            body="Notification service is available.",
            channel="push",
            payload={"source": "test_endpoint"},
        )
    )


@notification_router.get("/notifications/user/{user_id}", response_model=PaginatedNotifications)
async def list_user_notifications(
    user_id: int,
    service: NotificationServiceDep,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
) -> PaginatedNotifications:
    return await service.list_user_notifications(user_id=user_id, page=page, size=size)


@notification_router.post("/notifications/{notification_id}/retry", response_model=NotificationRead)
async def retry_notification(notification_id: int, service: NotificationServiceDep) -> NotificationRead:
    return await service.retry_notification(notification_id)
