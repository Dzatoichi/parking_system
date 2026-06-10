from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import WebSocket

from src.models.system_events import SystemEvent


class SystemEventWebSocketManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, payload: dict[str, Any]) -> None:
        disconnected: list[WebSocket] = []
        for websocket in list(self._connections):
            try:
                await websocket.send_json(payload)
            except Exception:
                disconnected.append(websocket)

        for websocket in disconnected:
            self.disconnect(websocket)

    async def broadcast_event(self, event: SystemEvent) -> None:
        await self.broadcast(
            {
                "type": "system_event_changed",
                "event": serialize_system_event(event),
                "parking_id": event.parking_id,
            }
        )


def serialize_system_event(event: SystemEvent) -> dict[str, Any]:
    created_at = event.created_at
    return {
        "id": event.id,
        "event_type": _serialize_value(event.event_type),
        "entity_type": _serialize_value(event.entity_type),
        "entity_id": event.entity_id,
        "parking_id": event.parking_id,
        "message": event.message,
        "payload": event.payload,
        "created_at": created_at.isoformat() if isinstance(created_at, datetime) else created_at,
    }


def _serialize_value(value: Any) -> Any:
    return getattr(value, "value", value)


system_event_ws_manager = SystemEventWebSocketManager()
