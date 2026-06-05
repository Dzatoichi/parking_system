from fastapi import APIRouter

from src.api.utils.dependencies import MonitoringServiceDep

monitoring_router = APIRouter(prefix="/v1/monitoring", tags=["monitoring"])


@monitoring_router.get("/status")
async def get_monitoring_status(service: MonitoringServiceDep) -> dict:
    return service.status()


@monitoring_router.post("/start")
async def start_monitoring(service: MonitoringServiceDep) -> dict:
    return service.start_monitoring()


@monitoring_router.post("/stop")
async def stop_monitoring(service: MonitoringServiceDep) -> dict:
    return service.stop_monitoring()


@monitoring_router.post("/markup/begin")
async def begin_markup(service: MonitoringServiceDep) -> dict:
    return service.begin_markup()


@monitoring_router.post("/markup/finish")
async def finish_markup(service: MonitoringServiceDep) -> dict:
    return service.finish_markup()
