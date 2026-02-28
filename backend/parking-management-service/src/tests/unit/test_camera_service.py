import pytest
from unittest.mock import AsyncMock
from fastapi import HTTPException

from src.services.camera_service import CameraService
from src.models.cameras import Cameras
from src.models.status.camera_status import CameraStatus
from src.schemas import CameraCreate, CameraUpdate


def _make_orm_camera(
    camera_id: int = 1,
    rtsp_url: str = "rtsp://192.168.1.10:554/stream",
    parking_id: int = 1,
    status: CameraStatus = CameraStatus.ACTIVE,
) -> Cameras:
    c = Cameras(rtsp_url=rtsp_url, parking_id=parking_id, status=status)
    c.id = camera_id
    c.position_x = None
    c.position_y = None
    return c


def _make_service():
    mock_session = AsyncMock()
    mock_session.commit = AsyncMock()
    service = CameraService(mock_session)
    service._dao = AsyncMock()
    service._parking_dao = AsyncMock()
    return service, mock_session


class TestCreateCamera:
    @pytest.mark.asyncio
    async def test_creates_successfully(self):
        service, mock_session = _make_service()
        service._parking_dao.get_by_id.return_value = object()  # парковка существует
        service._dao.get_by_rtsp.return_value = None
        service._dao.create.return_value = _make_orm_camera()

        result = await service.create_camera(
            1, CameraCreate(rtsp_url="rtsp://192.168.1.10:554/stream")
        )

        assert result.id == 1
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_raises_404_if_parking_missing(self):
        service, _ = _make_service()
        service._parking_dao.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc:
            await service.create_camera(99, CameraCreate(rtsp_url="rtsp://x:554/s"))

        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_raises_409_on_duplicate_url(self):
        service, _ = _make_service()
        service._parking_dao.get_by_id.return_value = object()
        service._dao.get_by_rtsp.return_value = _make_orm_camera()

        with pytest.raises(HTTPException) as exc:
            await service.create_camera(
                1, CameraCreate(rtsp_url="rtsp://192.168.1.10:554/stream")
            )

        assert exc.value.status_code == 409
        service._dao.create.assert_not_awaited()


class TestUpdateCamera:
    @pytest.mark.asyncio
    async def test_raises_404_when_not_found(self):
        service, _ = _make_service()
        service._dao.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc:
            await service.update_camera(99, CameraUpdate(position_x=1.0))

        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_no_op_on_empty_update(self):
        service, mock_session = _make_service()
        service._dao.get_by_id.return_value = _make_orm_camera()

        await service.update_camera(1, CameraUpdate())

        service._dao.update.assert_not_awaited()
        mock_session.commit.assert_not_awaited()


class TestDeleteCamera:
    @pytest.mark.asyncio
    async def test_deletes_successfully(self):
        service, mock_session = _make_service()
        service._dao.get_by_id.return_value = _make_orm_camera()

        await service.delete_camera(1)

        service._dao.delete.assert_awaited_once_with(1)
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_raises_404_when_not_found(self):
        service, _ = _make_service()
        service._dao.get_by_id.return_value = None

        with pytest.raises(HTTPException) as exc:
            await service.delete_camera(99)

        assert exc.value.status_code == 404