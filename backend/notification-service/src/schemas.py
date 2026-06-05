from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


Platform = Literal["ios", "android", "web"]
Channel = Literal["push", "email", "sms", "telegram", "in_app"]


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TokenRegister(BaseModel):
    user_id: int = Field(gt=0)
    platform: Platform
    token: str = Field(min_length=1, max_length=500)


class TokenRead(BaseSchema):
    id: int
    user_id: int
    platform: str
    token: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class NotificationCreate(BaseModel):
    user_id: int = Field(gt=0)
    type: str = Field(default="system", min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=1000)
    channel: Channel = "push"
    payload: dict[str, Any] | None = None


class NotificationRead(BaseSchema):
    id: int
    user_id: int
    channel: str
    type: str
    title: str
    body: str
    status: str
    payload: dict[str, Any] | None
    provider_message_id: str | None
    error_message: str | None
    created_at: datetime
    sent_at: datetime | None


class PaginatedNotifications(BaseModel):
    items: list[NotificationRead]
    total: int
    page: int
    size: int


class TemplateEvent(BaseModel):
    event_type: str = Field(min_length=1, max_length=64)
    user_id: int = Field(gt=0)
    payload: dict[str, Any] = Field(default_factory=dict)
