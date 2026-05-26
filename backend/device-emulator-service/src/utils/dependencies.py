from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.services.emulator_service import EmulatorService
from src.clients.events_client import EventsClient
from src.settings.config import settings

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_emulator_service(session: SessionDep) -> EmulatorService:
    return EmulatorService(session)

def get_events_client(
    base_url: str = settings.PARKING_MANAGMENT_SERVICE_URL.rstrip("/"),
    timeout: int = settings.PARKING_MANAGEMENT_TIMEOUT_SECONDS,
) -> EventsClient:
    return EventsClient(base_url=base_url,timeout=timeout)


EmulatorServiceDep = Annotated[EmulatorService, Depends(get_emulator_service)]
EventsClientDep = Annotated[EventsClient, Depends(get_events_client)]
