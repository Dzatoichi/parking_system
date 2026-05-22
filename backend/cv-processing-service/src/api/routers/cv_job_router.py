from fastapi import APIRouter, Header, Request, status

from src.api.schemas import CVJobCreate, CVJobRead
from src.api.utils.dependencies import CVJobServiceDep
from src.parking_monitor.core.frame_monitor import decode_test_detections_header

cv_job_router = APIRouter(prefix="/v1/jobs", tags=["cv-jobs"])


@cv_job_router.post("", response_model=CVJobRead, status_code=status.HTTP_201_CREATED)
async def create_job(body: CVJobCreate, service: CVJobServiceDep) -> CVJobRead:
    return await service.create_job(body)


@cv_job_router.get("/{job_id}", response_model=CVJobRead)
async def get_job(job_id: str, service: CVJobServiceDep) -> CVJobRead:
    return await service.get_job(job_id)


@cv_job_router.post("/{job_id}/stop", response_model=CVJobRead)
async def stop_job(job_id: str, service: CVJobServiceDep) -> CVJobRead:
    return await service.stop_job(job_id)


@cv_job_router.post("/{job_id}/frame")
async def push_frame(
    job_id: str,
    request: Request,
    service: CVJobServiceDep,
    x_test_detections: str | None = Header(default=None),
) -> dict:
    body = await request.body()
    test_detections = decode_test_detections_header(x_test_detections)
    return await service.process_frame(job_id, body, test_detections=test_detections)
