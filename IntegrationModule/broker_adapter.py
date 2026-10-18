"""Transport-neutral broker adapter contract; no Kafka/RabbitMQ dependency."""
from __future__ import annotations

import importlib
import os
import threading
import time
from typing import Iterable


class BrokerAdapter:
    """Implement consume(stop_event), publish(event), and close() for your broker."""
    def consume(self, stop_event: threading.Event) -> Iterable[dict]:
        raise NotImplementedError

    def publish(self, event: dict) -> None:
        raise NotImplementedError

    def close(self) -> None:
        pass


class BrokerAdapterStub(BrokerAdapter):
    """No-network placeholder for local runs and contract testing."""
    def consume(self, stop_event: threading.Event):
        while not stop_event.wait(0.25):
            continue
        return
        yield  # Make this a generator.

    def publish(self, event: dict) -> None:
        print("[BROKER OUTBOUND STUB]", event, flush=True)


def load_broker_adapter() -> BrokerAdapter:
    spec = os.getenv("PARKING_BROKER_ADAPTER", "").strip()
    if not spec:
        return BrokerAdapterStub()
    if ":" not in spec:
        raise ValueError("PARKING_BROKER_ADAPTER must be 'python.module:ClassName'")
    module_name, class_name = spec.split(":", 1)
    cls = getattr(importlib.import_module(module_name), class_name)
    adapter = cls()
    for method in ("consume", "publish", "close"):
        if not callable(getattr(adapter, method, None)):
            raise TypeError(f"Broker adapter must implement {method}()")
    return adapter
