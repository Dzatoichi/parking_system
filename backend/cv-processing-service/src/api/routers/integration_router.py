from fastapi import APIRouter
from src.services.spot_service import SpotService
from src.models.status.spot_status import SpotStatus

cv_router = APIRouter(prefix="/cv-events", tags=["cv-integration"])


#TODO: Внедрить зависимость сервиса парковочных мест

@cv_router.post("/vehicle-parked")
async def vehicle_parked(
    vehicle_id: int,
    spot_id: int,
    plate_number: str,
    service: SpotServiceDep
):
    """Обновить статус места когда ТС припаркован"""
    return await service.update_spot_status(
        spot_id,
        SpotStatus.OCCUPIED,
        {"vehicle_id": vehicle_id, "plate": plate_number}
    )

@cv_router.post("/vehicle-left")
async def vehicle_left(
    spot_id: int,
    service: SpotServiceDep
):
    """Обновить статус места когда ТС уехал"""
    return await service.update_spot_status(
        spot_id,
        SpotStatus.AVAILABLE
    )