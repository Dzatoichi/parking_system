import json
from collections.abc import Awaitable, Callable

import aio_pika
from aio_pika import ExchangeType, Message

from src.settings.config import settings


class BookingEventBroker:
    def __init__(self) -> None:
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractRobustChannel | None = None

    async def connect(self) -> None:
        if self._connection is not None and not self._connection.is_closed:
            return

        self._connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=10)

    async def close(self) -> None:
        if self._channel is not None and not self._channel.is_closed:
            await self._channel.close()
        if self._connection is not None and not self._connection.is_closed:
            await self._connection.close()

    async def publish(self, routing_key: str, payload: dict) -> None:
        await self.connect()
        assert self._channel is not None

        exchange = await self._channel.declare_exchange(
            settings.BOOKING_EVENTS_EXCHANGE,
            ExchangeType.TOPIC,
            durable=True,
        )
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        await exchange.publish(
            Message(body=body, content_type="application/json", delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
            routing_key=routing_key,
        )

    async def consume(self, handler: Callable[[dict], Awaitable[None]]) -> None:
        await self.connect()
        assert self._channel is not None

        exchange = await self._channel.declare_exchange(
            settings.BOOKING_EVENTS_EXCHANGE,
            ExchangeType.TOPIC,
            durable=True,
        )
        queue = await self._channel.declare_queue(settings.BOOKING_EVENTS_QUEUE, durable=True)
        await queue.bind(exchange, routing_key="booking.*")

        async with queue.iterator() as iterator:
            async for message in iterator:
                async with message.process():
                    payload = json.loads(message.body.decode("utf-8"))
                    await handler(payload)


class CVEventBroker:
    def __init__(self) -> None:
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractRobustChannel | None = None

    async def connect(self) -> None:
        if self._connection is not None and not self._connection.is_closed:
            return

        self._connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
        self._channel = await self._connection.channel()
        await self._channel.set_qos(prefetch_count=10)

    async def close(self) -> None:
        if self._channel is not None and not self._channel.is_closed:
            await self._channel.close()
        if self._connection is not None and not self._connection.is_closed:
            await self._connection.close()

    async def consume(self, handler: Callable[[dict], Awaitable[None]]) -> None:
        await self.connect()
        assert self._channel is not None

        exchange = await self._channel.declare_exchange(
            settings.CV_EVENTS_EXCHANGE,
            ExchangeType.TOPIC,
            durable=True,
        )
        queue = await self._channel.declare_queue(settings.CV_EVENTS_QUEUE, durable=True)
        await queue.bind(exchange, routing_key="cv.#")

        async with queue.iterator() as iterator:
            async for message in iterator:
                async with message.process():
                    payload = json.loads(message.body.decode("utf-8"))
                    await handler(payload)
