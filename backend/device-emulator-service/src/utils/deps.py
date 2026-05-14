from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.services.emulator_service import EmulatorService

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_emulator_service(session: SessionDep) -> EmulatorService:
    return EmulatorService(session)


EmulatorServiceDep = Annotated[EmulatorService, Depends(get_emulator_service)]
