import json
from typing import Any

import aio_pika
from aio_pika import ExchangeType, Message

from src.api.settings.config import settings


class CVEventBroker:
    def __init__(self) -> None:
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractRobustChannel | None = None

    async def connect(self) -> None:
        if self._connection is not None and not self._connection.is_closed:
            return

        self._connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        self._channel = await self._connection.channel()

    async def close(self) -> None:
        if self._channel is not None and not self._channel.is_closed:
            await self._channel.close()
        if self._connection is not None and not self._connection.is_closed:
            await self._connection.close()

    async def publish(self, routing_key: str, payload: dict[str, Any]) -> None:
        await self.connect()
        assert self._channel is not None

        exchange = await self._channel.declare_exchange(
            settings.CV_EVENTS_EXCHANGE,
            ExchangeType.TOPIC,
            durable=True,
        )
        body = json.dumps(payload, ensure_ascii=False, default=str).encode("utf-8")
        await exchange.publish(
            Message(
                body=body,
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=routing_key,
        )
