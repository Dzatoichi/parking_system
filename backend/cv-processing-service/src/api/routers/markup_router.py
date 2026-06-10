from typing import Any

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field

from src.api.utils.dependencies import MonitoringServiceDep

markup_router = APIRouter(prefix="/v1/markup", tags=["markup"])


class MarkupContainer(BaseModel):
    id: int | None = None
    spot_id: int | None = None
    name: str
    length: float = Field(gt=0)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    ground_points: list[list[float]] | None = Field(default=None, min_length=4, max_length=4)
    upper_points: list[list[float]] | None = Field(default=None, min_length=4, max_length=4)
    image_points: list[list[float]] | None = None
    is_base: bool = False


class MarkupSceneRequest(BaseModel):
    camera_id: int
    image_width: int | None = Field(default=None, gt=0)
    image_height: int | None = Field(default=None, gt=0)
    containers: list[MarkupContainer]


class MarkupSaveRequest(MarkupSceneRequest):
    replace_existing: bool = False


@markup_router.get("/cameras/{camera_id}/frame")
async def get_markup_camera_frame(camera_id: int, service: MonitoringServiceDep) -> Response:
    frame = service.get_camera_frame(camera_id)
    return Response(content=frame, media_type="image/jpeg")


@markup_router.post("/scene")
async def create_markup_scene(body: MarkupSceneRequest, service: MonitoringServiceDep) -> dict[str, Any]:
    return service.create_markup_scene(
        camera_id=body.camera_id,
        image_width=body.image_width,
        image_height=body.image_height,
        containers=[container.model_dump() for container in body.containers],
    )


@markup_router.post("/save")
async def save_markup(body: MarkupSaveRequest, service: MonitoringServiceDep) -> dict[str, Any]:
    return service.save_markup(
        camera_id=body.camera_id,
        containers=[container.model_dump() for container in body.containers],
        replace_existing=body.replace_existing,
    )
