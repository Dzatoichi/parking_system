from fastapi import APIRouter, Query

from src.schemas import CommandResultOut, IntegrationEventListOut, LightingSetBody, ParkingDevicesStateOut
from src.utils.dependencies import EmulatorServiceDep

emulator_router = APIRouter(prefix="/v1/parking/{parking_id}/devices", tags=["device-emulator"])


@emulator_router.get("/state", response_model=ParkingDevicesStateOut)
async def get_devices_state(parking_id: int, svc: EmulatorServiceDep) -> ParkingDevicesStateOut:
    return await svc.get_state(parking_id)


@emulator_router.post("/barrier/open", response_model=CommandResultOut)
async def barrier_open(
    parking_id: int,
    svc: EmulatorServiceDep,
    simulate_unreachable: bool = Query(default=False, description="Симуляция недоступности устройства (FT-6.8)"),
) -> CommandResultOut:
    return await svc.open_barrier(parking_id, simulate_unreachable=simulate_unreachable)


@emulator_router.post("/barrier/close", response_model=CommandResultOut)
async def barrier_close(
    parking_id: int,
    svc: EmulatorServiceDep,
    simulate_unreachable: bool = Query(default=False),
) -> CommandResultOut:
    return await svc.close_barrier(parking_id, simulate_unreachable=simulate_unreachable)


@emulator_router.post("/lighting", response_model=CommandResultOut)
async def set_lighting(parking_id: int, body: LightingSetBody, svc: EmulatorServiceDep) -> CommandResultOut:
    return await svc.set_lighting(parking_id, body)


@emulator_router.get("/events", response_model=IntegrationEventListOut)
async def list_integration_events(
    parking_id: int,
    svc: EmulatorServiceDep,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
) -> IntegrationEventListOut:
    return await svc.list_events(parking_id, page=page, size=size)
