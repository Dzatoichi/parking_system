import asyncio

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from src.schemas import PaginatedResponse
from src.schemas.events_schemas import SystemEventReadSchema, SystemEventCreateSchema
from src.services.system_event_ws import system_event_ws_manager
from src.utils.dependencies import EventServiceDep

events_router = APIRouter(prefix="/events", tags=["events"])


@events_router.websocket("/ws")
async def events_ws(websocket: WebSocket) -> None:
    await system_event_ws_manager.connect(websocket)
    try:
        await websocket.send_json({"type": "events_connected"})
        while True:
            await asyncio.sleep(30)
            await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        return
    except Exception:
        return
    finally:
        system_event_ws_manager.disconnect(websocket)

@events_router.get(
    path="",
    response_model=PaginatedResponse[SystemEventReadSchema],
    summary="Получение всех событий",
)
async def get_events(
    parking_id: int,
    service: EventServiceDep,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=50, ge=1, le=200),
) -> PaginatedResponse[SystemEventReadSchema]:
    return await service.get_all_paginated(
        parking_id=parking_id,
        page=page,
        size=size,
    )


@events_router.get(
    path="/{event_id}",
    response_model=SystemEventReadSchema,
    summary="Событие по id",
)
async def get_event(
    event_id: int,
    service: EventServiceDep,
) -> SystemEventReadSchema:
    return await service.get_by_id(event_id=event_id)

@events_router.post(
    path="",
    response_model=SystemEventReadSchema,
    summary="Создание события",
)
async def create_event(
    data: SystemEventCreateSchema,
    service: EventServiceDep,
) -> SystemEventReadSchema:
    return await service.add_event(data)
