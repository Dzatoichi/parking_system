from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func

from src.models.cameras import Cameras
from src.models.status.camera_status import CameraStatus


class CameraDAO:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session


    async def get_by_id(self, camera_id: int) -> Optional[Cameras]:
        result = await self._session.execute(
            select(Cameras).where(Cameras.id == camera_id)
        )
        return result.scalar_one_or_none()

    async def get_by_parking(
        self,
        parking_id: int,
        status: Optional[CameraStatus] = None,
        offset: int = 0,
        limit: int = 100,
    ) -> tuple[list[Cameras], int]:
        conditions = [Cameras.parking_id == parking_id]
        if status is not None:
            conditions.append(Cameras.status == status)

        from sqlalchemy import and_
        where = and_(*conditions)

        rows = await self._session.execute(
            select(Cameras).where(where).offset(offset).limit(limit)
        )
        total = await self._session.execute(
            select(func.count(Cameras.id)).where(where)
        )
        return list(rows.scalars().all()), total.scalar_one()

    async def get_by_rtsp(self, rtsp_url: str) -> Optional[Cameras]:
        result = await self._session.execute(
            select(Cameras).where(Cameras.rtsp_url == rtsp_url)
        )
        return result.scalar_one_or_none()


    async def create(self, camera: Cameras) -> Cameras:
        self._session.add(camera)
        await self._session.flush()
        await self._session.refresh(camera)
        return camera

    async def update(self, camera_id: int, values: dict) -> Optional[Cameras]:
        result = await self._session.execute(
            update(Cameras)
            .where(Cameras.id == camera_id)
            .values(**values)
            .returning(Cameras)
        )
        return result.scalar_one_or_none()

    async def delete(self, camera_id: int) -> bool:
        camera = await self.get_by_id(camera_id)
        if camera is None:
            return False
        await self._session.delete(camera)
        await self._session.flush()
        return True