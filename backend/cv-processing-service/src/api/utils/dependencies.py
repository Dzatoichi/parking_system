from typing import Annotated

from fastapi import Depends

from src.api.brokers.cv_event_broker import CVEventBroker
from src.api.clients.parking_management_client import ParkingManagementClient
from src.api.repositories.cv_job_repository import CVJobRepository
from src.api.services.cv_job_service import CVJobService
from src.parking_monitor.core.frame_monitor import FrameParkingMonitor

_cv_job_repository = CVJobRepository()
_parking_management_client = ParkingManagementClient()
_cv_event_broker = CVEventBroker()
_frame_monitor = FrameParkingMonitor()


def get_cv_job_service() -> CVJobService:
    return CVJobService(
        repository=_cv_job_repository,
        parking_client=_parking_management_client,
        event_broker=_cv_event_broker,
        monitor=_frame_monitor,
    )


CVJobServiceDep = Annotated[CVJobService, Depends(get_cv_job_service)]
