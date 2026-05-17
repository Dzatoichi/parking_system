from fastapi import APIRouter, Query

from src.models.system_events import SystemEvent
from src.schemas import PaginatedResponse
from src.schemas.events_schemas import SystemEventReadSchema
from src.utils.dependencies import EventServiceDep

events_router = APIRouter(prefix="/events", tags=["events"])

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
    return await service.get_all_paginated_by_parking(
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
    return await service.get_event(event_id=event_id)