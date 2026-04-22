from fastapi import APIRouter

from src.schemas import AnalyticsOverview
from src.utils.dependencies import AnalyticsServiceDep

analytics_router = APIRouter(prefix="/analytics", tags=["analytics"])


@analytics_router.get("/{parking_id}/overview", response_model=AnalyticsOverview)
async def get_overview(
    parking_id: int,
    service: AnalyticsServiceDep,
) -> AnalyticsOverview:
    return await service.get_overview(parking_id)
