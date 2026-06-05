from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


PaymentStatus = Literal["pending", "succeeded", "failed", "cancelled", "refunded"]
FineStatus = Literal["pending", "paid", "cancelled"]


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class PaymentCreate(BaseModel):
    user_id: int = Field(gt=0)
    amount: float = Field(gt=0)
    currency: str = Field(default="RUB", min_length=3, max_length=3)
    booking_id: int | None = Field(default=None, gt=0)
    fine_id: int | None = Field(default=None, gt=0)
    description: str | None = Field(default=None, max_length=500)
    metadata: dict[str, Any] | None = None


class PaymentRead(BaseSchema):
    id: int
    booking_id: int | None
    fine_id: int | None
    user_id: int
    amount: float
    currency: str
    status: str
    provider: str
    provider_payment_id: str | None
    payment_url: str | None
    description: str | None
    metadata: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class FineCreate(BaseModel):
    user_id: int = Field(gt=0)
    amount: float = Field(gt=0)
    reason: str = Field(min_length=1, max_length=500)
    currency: str = Field(default="RUB", min_length=3, max_length=3)
    vehicle_id: int | None = Field(default=None, gt=0)
    booking_id: int | None = Field(default=None, gt=0)
    spot_id: int | None = Field(default=None, gt=0)
    violation_id: int | None = Field(default=None, gt=0)
    metadata: dict[str, Any] | None = None


class FineRead(BaseSchema):
    id: int
    user_id: int
    vehicle_id: int | None
    booking_id: int | None
    spot_id: int | None
    violation_id: int | None
    amount: float
    currency: str
    reason: str
    status: str
    metadata: dict[str, Any] | None = None
    created_at: datetime
    paid_at: datetime | None


class PaymentEventRead(BaseSchema):
    id: int
    event_type: str
    payment_id: int | None
    fine_id: int | None
    booking_id: int | None
    payload: dict[str, Any] | None
    created_at: datetime


class PaginatedPaymentEvents(BaseModel):
    items: list[PaymentEventRead]
    total: int
    page: int
    size: int


class MockWebhookBody(BaseModel):
    provider_payment_id: str
    status: PaymentStatus
    payload: dict[str, Any] | None = None


class FinePaymentResult(BaseModel):
    fine: FineRead
    payment: PaymentRead
