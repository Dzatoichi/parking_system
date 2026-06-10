from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.services.emulator_service import EmulatorService
from src.services.event_producer import EventProducer
from src.clients.events_client import EventsClient
from src.settings.config import settings

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_events_client(
    base_url: str = settings.PARKING_MANAGEMENT_SERVICE_URL.rstrip("/"),
    timeout: int = settings.PARKING_MANAGEMENT_TIMEOUT_SECONDS,
) -> EventsClient:
    return EventsClient(base_url=base_url,timeout=timeout)

def get_event_producer(events_client: EventsClient = Depends(get_events_client)) -> EventProducer:
    return EventProducer(events_client)

def get_emulator_service(
    session: SessionDep,
    event_producer: EventProducer = Depends(get_event_producer),
) -> EmulatorService:
    return EmulatorService(session, event_producer)


EmulatorServiceDep = Annotated[EmulatorService, Depends(get_emulator_service)]
EventsClientDep = Annotated[EventsClient, Depends(get_events_client)]
