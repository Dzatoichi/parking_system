from fastapi import APIRouter, Query, status

from src.schemas import (
    FineCreate,
    FinePaymentResult,
    FineRead,
    MockWebhookBody,
    PaginatedPaymentEvents,
    PaymentCreate,
    PaymentRead,
)
from src.utils.dependencies import PaymentServiceDep


payment_router = APIRouter(tags=["payments"])


@payment_router.post("/payments", response_model=PaymentRead, status_code=status.HTTP_201_CREATED)
async def create_payment(body: PaymentCreate, service: PaymentServiceDep) -> PaymentRead:
    return await service.create_payment(body)


@payment_router.get("/payments/{payment_id}", response_model=PaymentRead)
async def get_payment(payment_id: int, service: PaymentServiceDep) -> PaymentRead:
    return await service.get_payment(payment_id)


@payment_router.get("/payments/user/{user_id}", response_model=list[PaymentRead])
async def list_user_payments(user_id: int, service: PaymentServiceDep) -> list[PaymentRead]:
    return await service.list_user_payments(user_id)


@payment_router.post("/payments/{payment_id}/confirm", response_model=PaymentRead)
async def confirm_payment(payment_id: int, service: PaymentServiceDep) -> PaymentRead:
    return await service.set_payment_status(payment_id, "succeeded")


@payment_router.post("/payments/{payment_id}/fail", response_model=PaymentRead)
async def fail_payment(payment_id: int, service: PaymentServiceDep) -> PaymentRead:
    return await service.set_payment_status(payment_id, "failed")


@payment_router.post("/payments/{payment_id}/cancel", response_model=PaymentRead)
async def cancel_payment(payment_id: int, service: PaymentServiceDep) -> PaymentRead:
    return await service.set_payment_status(payment_id, "cancelled")


@payment_router.post("/payments/{payment_id}/refund", response_model=PaymentRead)
async def refund_payment(payment_id: int, service: PaymentServiceDep) -> PaymentRead:
    return await service.set_payment_status(payment_id, "refunded")


@payment_router.post("/webhooks/mock", response_model=PaymentRead)
async def mock_webhook(body: MockWebhookBody, service: PaymentServiceDep) -> PaymentRead:
    return await service.apply_mock_webhook(body)


@payment_router.post("/fines", response_model=FineRead, status_code=status.HTTP_201_CREATED)
async def create_fine(body: FineCreate, service: PaymentServiceDep) -> FineRead:
    return await service.create_fine(body)


@payment_router.get("/fines/{fine_id}", response_model=FineRead)
async def get_fine(fine_id: int, service: PaymentServiceDep) -> FineRead:
    return await service.get_fine(fine_id)


@payment_router.get("/fines/user/{user_id}", response_model=list[FineRead])
async def list_user_fines(user_id: int, service: PaymentServiceDep) -> list[FineRead]:
    return await service.list_user_fines(user_id)


@payment_router.post("/fines/{fine_id}/pay", response_model=FinePaymentResult)
async def create_fine_payment(fine_id: int, service: PaymentServiceDep) -> FinePaymentResult:
    return await service.create_fine_payment(fine_id)


@payment_router.get("/payment-events", response_model=PaginatedPaymentEvents)
async def list_events(
    service: PaymentServiceDep,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
) -> PaginatedPaymentEvents:
    return await service.list_events(page=page, size=size)
