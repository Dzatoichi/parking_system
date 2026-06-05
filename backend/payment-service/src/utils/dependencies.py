from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.db import get_session
from src.services.payment_service import PaymentService


SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_payment_service(session: SessionDep) -> PaymentService:
    return PaymentService(session)


PaymentServiceDep = Annotated[PaymentService, Depends(get_payment_service)]
