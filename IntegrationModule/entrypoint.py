"""External integration entry point for the existing parking controller.

Run: python -m IntegrationModule.entrypoint
Set PARKING_BROKER_ADAPTER=your_package.module:YourAdapter when the broker
adapter is implemented by the backend team.
"""
from __future__ import annotations

import signal
import threading
import traceback

from IntegrationModule.broker_adapter import load_broker_adapter
from IntegrationModule.search_registry import get_registry


def main() -> None:
    from run_main_controller import main as controller_main

    stop_event = threading.Event()
    adapter = load_broker_adapter()
    registry = get_registry()
    registry.set_event_sink(adapter.publish)

    def stop_handler(_signum, _frame):
        stop_event.set()

    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)

    def consume_requests() -> None:
        try:
            for message in adapter.consume(stop_event):
                if stop_event.is_set():
                    break
                if not isinstance(message, dict):
                    print("[BROKER INBOUND] ignored non-object message", flush=True)
                    continue
                event = message.get("event", "vehicle_search_request")
                if event not in {"vehicle_search_request", "search_request"}:
                    print(f"[BROKER INBOUND] ignored event={event!r}", flush=True)
                    continue
                try:
                    registry.add_request(message)
                    print(f"[BROKER INBOUND] accepted search_id={message.get('search_id')!r}", flush=True)
                except (TypeError, ValueError) as exc:
                    print(f"[BROKER INBOUND] invalid request: {exc}", flush=True)
        except Exception:
            if not stop_event.is_set():
                traceback.print_exc()
                stop_event.set()

    worker = threading.Thread(target=consume_requests, name="parking-broker-consumer", daemon=True)
    worker.start()
    try:
        # Existing controller remains the single owner of the camera pipeline.
        controller_main()
    finally:
        stop_event.set()
        adapter.close()
        worker.join(timeout=2.0)
        registry.set_event_sink(None)


if __name__ == "__main__":
    main()
