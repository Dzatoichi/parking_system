from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.fcm_client import FCMClient
from src.models import Notification, NotificationToken
from src.schemas import (
    NotificationCreate,
    NotificationRead,
    PaginatedNotifications,
    TemplateEvent,
    TokenRead,
    TokenRegister,
)
from src.settings.config import settings


class NotificationService:
    def __init__(self, session: AsyncSession, fcm_client: FCMClient | None = None) -> None:
        self._session = session
        self._fcm_client = fcm_client

    async def register_token(self, body: TokenRegister) -> TokenRead:
        now = datetime.now(tz=timezone.utc)
        stmt = (
            sqlite_insert(NotificationToken)
            .values(
                user_id=body.user_id,
                platform=body.platform,
                token=body.token,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["token"],
                set_={
                    "user_id": body.user_id,
                    "platform": body.platform,
                    "is_active": True,
                    "updated_at": now,
                },
            )
        )
        await self._session.execute(stmt)
        await self._session.commit()
        result = await self._session.execute(select(NotificationToken).where(NotificationToken.token == body.token))
        token = result.scalar_one()
        return self._token_to_read(token)

    async def unregister_token(self, token: str) -> TokenRead:
        result = await self._session.execute(select(NotificationToken).where(NotificationToken.token == token))
        row = result.scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Token not found")
        row.is_active = False
        row.updated_at = datetime.now(tz=timezone.utc)
        await self._session.commit()
        await self._session.refresh(row)
        return self._token_to_read(row)

    async def list_user_tokens(self, user_id: int) -> list[TokenRead]:
        result = await self._session.execute(
            select(NotificationToken).where(NotificationToken.user_id == user_id).order_by(NotificationToken.id.desc())
        )
        return [self._token_to_read(row) for row in result.scalars().all()]

    async def send_notification(self, body: NotificationCreate) -> NotificationRead:
        notification = Notification(
            user_id=body.user_id,
            channel=body.channel,
            type=body.type,
            title=body.title,
            body=body.body,
            status="pending",
            payload=body.payload,
        )
        self._session.add(notification)
        await self._session.flush()
        await self._deliver(notification)
        await self._session.commit()
        await self._session.refresh(notification)
        return self._notification_to_read(notification)

    async def send_from_event(self, body: TemplateEvent) -> NotificationRead:
        title, text = self._render_template(body.event_type, body.payload)
        return await self.send_notification(
            NotificationCreate(
                user_id=body.user_id,
                type=body.event_type,
                title=title,
                body=text,
                channel="push",
                payload=body.payload,
            )
        )

    async def list_user_notifications(self, user_id: int, page: int, size: int) -> PaginatedNotifications:
        offset = (page - 1) * size
        count_stmt = select(func.count(Notification.id)).where(Notification.user_id == user_id)
        stmt = (
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
            .offset(offset)
            .limit(size)
        )
        total = (await self._session.execute(count_stmt)).scalar_one()
        rows = (await self._session.execute(stmt)).scalars().all()
        return PaginatedNotifications(
            items=[self._notification_to_read(row) for row in rows],
            total=int(total),
            page=page,
            size=size,
        )

    async def retry_notification(self, notification_id: int) -> NotificationRead:
        notification = await self._get_notification(notification_id)
        if notification.status == "sent":
            return self._notification_to_read(notification)
        await self._deliver(notification)
        await self._session.commit()
        await self._session.refresh(notification)
        return self._notification_to_read(notification)

    async def _deliver(self, notification: Notification) -> None:
        if notification.channel != "push" or settings.push_provider == "mock":
            await self._deliver_mock(notification)
            return
        if settings.push_provider != "fcm":
            notification.status = "failed"
            notification.error_message = f"Unsupported push provider: {settings.push_provider}"
            return
        await self._deliver_fcm(notification)

    async def _deliver_fcm(self, notification: Notification) -> None:
        result = await self._session.execute(
            select(NotificationToken).where(
                NotificationToken.user_id == notification.user_id,
                NotificationToken.is_active.is_(True),
            )
        )
        tokens = result.scalars().all()
        if not tokens:
            notification.status = "failed"
            notification.error_message = "No active push token for user"
            return

        if self._fcm_client is None:
            notification.status = "failed"
            notification.error_message = "FCM client is not configured"
            return

        successes: list[str] = []
        failures: list[str] = []
        for token in tokens:
            delivery = await self._fcm_client.send(
                token=token.token,
                title=notification.title,
                body=notification.body,
                data={
                    "notification_id": notification.id,
                    "type": notification.type,
                    **(notification.payload or {}),
                },
            )
            if delivery.success:
                if delivery.provider_message_id:
                    successes.append(delivery.provider_message_id)
            else:
                failures.append(delivery.error_message or "Unknown FCM error")

        notification.sent_at = datetime.now(tz=timezone.utc)
        if successes:
            notification.status = "sent"
            notification.provider_message_id = ",".join(successes[:3])
            notification.error_message = "; ".join(failures[:2]) if failures else None
            return
        notification.status = "failed"
        notification.error_message = "; ".join(failures[:3]) if failures else "FCM delivery failed"

    async def _deliver_mock(self, notification: Notification) -> None:
        notification.sent_at = datetime.now(tz=timezone.utc)
        notification.status = "sent"
        notification.provider_message_id = f"mock_{uuid4().hex}"
        notification.error_message = None

    async def _get_notification(self, notification_id: int) -> Notification:
        notification = await self._session.get(Notification, notification_id)
        if notification is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
        return notification

    @staticmethod
    def _render_template(event_type: str, payload: dict) -> tuple[str, str]:
        if event_type == "payment.succeeded":
            return "Payment confirmed", f"Payment #{payload.get('payment_id', '')} was confirmed."
        if event_type == "payment.failed":
            return "Payment failed", "Payment was not completed. Please try again."
        if event_type == "fine.created":
            return "Fine created", f"Fine amount: {payload.get('amount', '')} {payload.get('currency', 'RUB')}."
        if event_type == "booking.confirmed":
            return "Booking confirmed", f"Booking #{payload.get('booking_id', '')} is active."
        if event_type == "spot.status_changed":
            return "Parking spot updated", f"Spot #{payload.get('spot_id', '')} status changed."
        return "Parking notification", "There is a new event in the parking system."

    @staticmethod
    def _token_to_read(token: NotificationToken) -> TokenRead:
        return TokenRead(
            id=token.id,
            user_id=token.user_id,
            platform=token.platform,
            token=token.token,
            is_active=token.is_active,
            created_at=token.created_at,
            updated_at=token.updated_at,
        )

    @staticmethod
    def _notification_to_read(notification: Notification) -> NotificationRead:
        return NotificationRead(
            id=notification.id,
            user_id=notification.user_id,
            channel=notification.channel,
            type=notification.type,
            title=notification.title,
            body=notification.body,
            status=notification.status,
            payload=notification.payload,
            provider_message_id=notification.provider_message_id,
            error_message=notification.error_message,
            created_at=notification.created_at,
            sent_at=notification.sent_at,
        )
