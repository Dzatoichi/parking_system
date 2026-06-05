from datetime import datetime, timezone
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Fine, Payment, PaymentEvent
from src.schemas import (
    FineCreate,
    FinePaymentResult,
    FineRead,
    MockWebhookBody,
    PaginatedPaymentEvents,
    PaymentCreate,
    PaymentEventRead,
    PaymentRead,
)
from src.settings.config import settings


class PaymentService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_payment(self, body: PaymentCreate) -> PaymentRead:
        provider_payment_id = f"mock_{uuid4().hex}"
        payment = Payment(
            booking_id=body.booking_id,
            fine_id=body.fine_id,
            user_id=body.user_id,
            amount=body.amount,
            currency=body.currency.upper(),
            status="pending",
            provider="mock",
            provider_payment_id=provider_payment_id,
            payment_url=f"{settings.mock_payment_base_url}/{provider_payment_id}",
            description=body.description,
            metadata_=body.metadata,
        )
        self._session.add(payment)
        await self._session.flush()
        self._add_event("payment.created", payment=payment, payload=self._payment_payload(payment))
        await self._session.commit()
        await self._session.refresh(payment)
        return self._payment_to_read(payment)

    async def get_payment(self, payment_id: int) -> PaymentRead:
        return self._payment_to_read(await self._get_payment(payment_id))

    async def list_user_payments(self, user_id: int) -> list[PaymentRead]:
        result = await self._session.execute(select(Payment).where(Payment.user_id == user_id).order_by(Payment.id.desc()))
        return [self._payment_to_read(row) for row in result.scalars().all()]

    async def set_payment_status(self, payment_id: int, new_status: str) -> PaymentRead:
        payment = await self._get_payment(payment_id)
        if payment.status in {"cancelled", "refunded"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Payment is {payment.status}")
        if payment.status == "succeeded" and new_status not in {"refunded", "succeeded"}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Succeeded payment can only be refunded")

        payment.status = new_status
        payment.updated_at = datetime.now(tz=timezone.utc)
        if payment.fine_id is not None and new_status == "succeeded":
            fine = await self._session.get(Fine, payment.fine_id)
            if fine is not None:
                fine.status = "paid"
                fine.paid_at = payment.updated_at
                self._add_event("fine.paid", payment=payment, fine=fine, payload=self._fine_payload(fine))
        self._add_event(f"payment.{new_status}", payment=payment, payload=self._payment_payload(payment))
        await self._session.commit()
        await self._session.refresh(payment)
        return self._payment_to_read(payment)

    async def apply_mock_webhook(self, body: MockWebhookBody) -> PaymentRead:
        result = await self._session.execute(
            select(Payment).where(Payment.provider_payment_id == body.provider_payment_id)
        )
        payment = result.scalar_one_or_none()
        if payment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
        return await self.set_payment_status(payment.id, body.status)

    async def create_fine(self, body: FineCreate) -> FineRead:
        fine = Fine(
            user_id=body.user_id,
            vehicle_id=body.vehicle_id,
            booking_id=body.booking_id,
            spot_id=body.spot_id,
            violation_id=body.violation_id,
            amount=body.amount,
            currency=body.currency.upper(),
            reason=body.reason,
            status="pending",
            metadata_=body.metadata,
        )
        self._session.add(fine)
        await self._session.flush()
        self._add_event("fine.created", fine=fine, payload=self._fine_payload(fine))
        await self._session.commit()
        await self._session.refresh(fine)
        return self._fine_to_read(fine)

    async def get_fine(self, fine_id: int) -> FineRead:
        return self._fine_to_read(await self._get_fine(fine_id))

    async def list_user_fines(self, user_id: int) -> list[FineRead]:
        result = await self._session.execute(select(Fine).where(Fine.user_id == user_id).order_by(Fine.id.desc()))
        return [self._fine_to_read(row) for row in result.scalars().all()]

    async def create_fine_payment(self, fine_id: int) -> FinePaymentResult:
        fine = await self._get_fine(fine_id)
        if fine.status == "paid":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Fine is already paid")
        payment = await self.create_payment(
            PaymentCreate(
                user_id=fine.user_id,
                amount=fine.amount,
                currency=fine.currency,
                fine_id=fine.id,
                booking_id=fine.booking_id,
                description=f"Fine payment: {fine.reason}",
                metadata={"spot_id": fine.spot_id, "vehicle_id": fine.vehicle_id, "violation_id": fine.violation_id},
            )
        )
        return FinePaymentResult(fine=self._fine_to_read(fine), payment=payment)

    async def list_events(self, page: int, size: int) -> PaginatedPaymentEvents:
        offset = (page - 1) * size
        total = (await self._session.execute(select(func.count(PaymentEvent.id)))).scalar_one()
        result = await self._session.execute(
            select(PaymentEvent).order_by(PaymentEvent.created_at.desc()).offset(offset).limit(size)
        )
        return PaginatedPaymentEvents(
            items=[self._event_to_read(row) for row in result.scalars().all()],
            total=int(total),
            page=page,
            size=size,
        )

    async def _get_payment(self, payment_id: int) -> Payment:
        payment = await self._session.get(Payment, payment_id)
        if payment is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
        return payment

    async def _get_fine(self, fine_id: int) -> Fine:
        fine = await self._session.get(Fine, fine_id)
        if fine is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Fine not found")
        return fine

    def _add_event(
        self,
        event_type: str,
        *,
        payment: Payment | None = None,
        fine: Fine | None = None,
        payload: dict | None = None,
    ) -> None:
        self._session.add(
            PaymentEvent(
                event_type=event_type,
                payment_id=payment.id if payment else None,
                fine_id=(fine.id if fine else payment.fine_id if payment else None),
                booking_id=(payment.booking_id if payment else fine.booking_id if fine else None),
                payload=payload,
            )
        )

    @staticmethod
    def _payment_payload(payment: Payment) -> dict:
        return {
            "payment_id": payment.id,
            "booking_id": payment.booking_id,
            "fine_id": payment.fine_id,
            "user_id": payment.user_id,
            "amount": payment.amount,
            "currency": payment.currency,
            "status": payment.status,
            "provider_payment_id": payment.provider_payment_id,
        }

    @staticmethod
    def _fine_payload(fine: Fine) -> dict:
        return {
            "fine_id": fine.id,
            "user_id": fine.user_id,
            "vehicle_id": fine.vehicle_id,
            "booking_id": fine.booking_id,
            "spot_id": fine.spot_id,
            "amount": fine.amount,
            "currency": fine.currency,
            "status": fine.status,
            "reason": fine.reason,
        }

    @staticmethod
    def _payment_to_read(payment: Payment) -> PaymentRead:
        return PaymentRead(
            id=payment.id,
            booking_id=payment.booking_id,
            fine_id=payment.fine_id,
            user_id=payment.user_id,
            amount=payment.amount,
            currency=payment.currency,
            status=payment.status,
            provider=payment.provider,
            provider_payment_id=payment.provider_payment_id,
            payment_url=payment.payment_url,
            description=payment.description,
            metadata=payment.metadata_,
            created_at=payment.created_at,
            updated_at=payment.updated_at,
        )

    @staticmethod
    def _fine_to_read(fine: Fine) -> FineRead:
        return FineRead(
            id=fine.id,
            user_id=fine.user_id,
            vehicle_id=fine.vehicle_id,
            booking_id=fine.booking_id,
            spot_id=fine.spot_id,
            violation_id=fine.violation_id,
            amount=fine.amount,
            currency=fine.currency,
            reason=fine.reason,
            status=fine.status,
            metadata=fine.metadata_,
            created_at=fine.created_at,
            paid_at=fine.paid_at,
        )

    @staticmethod
    def _event_to_read(event: PaymentEvent) -> PaymentEventRead:
        return PaymentEventRead(
            id=event.id,
            event_type=event.event_type,
            payment_id=event.payment_id,
            fine_id=event.fine_id,
            booking_id=event.booking_id,
            payload=event.payload,
            created_at=event.created_at,
        )
