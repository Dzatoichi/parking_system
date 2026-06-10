"""Бизнес-логика эмуляторов шлагбаума и освещения."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import EmulatedDevice, IntegrationDeviceEvent
from src.schemas import (
    BarrierStateOut,
    CommandResultOut,
    IntegrationEventListOut,
    IntegrationEventOut,
    LightingSetBody,
    LightingStateOut,
    ParkingDevicesStateOut,
    EventType,
    SystemEventCreateSchema,
)
from src.services.event_producer import EventProducer

KIND_BARRIER = "barrier"
KIND_LIGHTING = "lighting"


def _default_barrier_state() -> dict[str, Any]:
    return {"position": "closed"}


def _default_lighting_state() -> dict[str, Any]:
    return {"on": False, "brightness": 0}


class EmulatorService:
    def __init__(self, session: AsyncSession, event_producer: EventProducer | None = None) -> None:
        self._session = session
        self._event_producer = event_producer

    async def _get_device_row(self, parking_id: int, device_kind: str) -> EmulatedDevice | None:
        stmt = select(EmulatedDevice).where(
            EmulatedDevice.parking_id == parking_id,
            EmulatedDevice.device_kind == device_kind,
        )
        res = await self._session.execute(stmt)
        return res.scalar_one_or_none()

    async def _upsert_state(self, parking_id: int, device_kind: str, state: dict[str, Any]) -> None:
        now = datetime.now(tz=timezone.utc)
        stmt = (
            sqlite_insert(EmulatedDevice)
            .values(
                parking_id=parking_id,
                device_kind=device_kind,
                state=state,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["parking_id", "device_kind"],
                set_={"state": state, "updated_at": now},
            )
        )
        await self._session.execute(stmt)
        await self._session.commit()

    async def _append_event(
        self,
        *,
        parking_id: int,
        device_kind: str,
        action: str,
        request_payload: dict[str, Any] | None,
        response_payload: dict[str, Any] | None,
        success: bool,
        error_message: str | None,
    ) -> IntegrationDeviceEvent:
        ev = IntegrationDeviceEvent(
            parking_id=parking_id,
            device_kind=device_kind,
            action=action,
            request_payload=request_payload,
            response_payload=response_payload,
            success=success,
            error_message=error_message,
            created_at=datetime.now(tz=timezone.utc),
        )
        self._session.add(ev)
        await self._session.commit()
        await self._session.refresh(ev)
        return ev

    async def _publish_device_event(
        self,
        event: IntegrationDeviceEvent,
        *,
        event_type: str,
        message: str,
    ) -> None:
        if self._event_producer is None:
            return

        try:
            await self._event_producer.send_device_event(
                SystemEventCreateSchema(
                    event_type=event_type,
                    entity_type=event.device_kind,
                    entity_id=event.id,
                    parking_id=event.parking_id,
                    message=message,
                    payload={
                        "device_event_id": event.id,
                        "device_kind": event.device_kind,
                        "action": event.action,
                        "success": event.success,
                        "error_message": event.error_message,
                        "request_payload": event.request_payload,
                        "response_payload": event.response_payload,
                    },
                )
            )
        except Exception:
            return

    async def get_state(self, parking_id: int) -> ParkingDevicesStateOut:
        barrier_row = await self._get_device_row(parking_id, KIND_BARRIER)
        lighting_row = await self._get_device_row(parking_id, KIND_LIGHTING)
        b = barrier_row.state if barrier_row else _default_barrier_state()
        l_ = lighting_row.state if lighting_row else _default_lighting_state()
        return ParkingDevicesStateOut(
            parking_id=parking_id,
            barrier=BarrierStateOut(position=str(b.get("position", "closed"))),
            lighting=LightingStateOut(on=bool(l_.get("on", False)), brightness=int(l_.get("brightness", 0))),
        )

    async def open_barrier(self, parking_id: int, *, simulate_unreachable: bool = False) -> CommandResultOut:
        req = {"simulate_unreachable": simulate_unreachable}
        if simulate_unreachable:
            event = await self._append_event(
                parking_id=parking_id,
                device_kind=KIND_BARRIER,
                action="barrier_open",
                request_payload=req,
                response_payload=None,
                success=False,
                error_message="Эмулятор: устройство недоступно (тестовый режим)",
            )
            await self._publish_device_event(event, event_type=EventType.DEVICE_UNAVAILABLE.value, message="device unavailable")
            st = (await self._get_device_row(parking_id, KIND_BARRIER))
            cur = st.state if st else _default_barrier_state()
            return CommandResultOut(
                success=False,
                parking_id=parking_id,
                device_kind=KIND_BARRIER,
                action="barrier_open",
                state=cur,
                message="Устройство недоступно (симуляция)",
            )
        new_state = {"position": "open"}
        # system_event = SystemEventCreateSchema(
        #     event_type=EventType.BARRIER_OPENED,
        #     entity_type=KIND_BARRIER,
        #     entity_id=_id,
        # )
        await self._upsert_state(parking_id, KIND_BARRIER, new_state)
        # await self._event_producer
        event = await self._append_event(
            parking_id=parking_id,
            device_kind=KIND_BARRIER,
            action="barrier_open",
            request_payload=req,
            response_payload=new_state,
            success=True,
            error_message=None,
        )
        await self._publish_device_event(event, event_type=EventType.BARRIER_OPENED.value, message="barrier opened")
        return CommandResultOut(
            success=True,
            parking_id=parking_id,
            device_kind=KIND_BARRIER,
            action="barrier_open",
            state=new_state,
            message=None,
        )

    async def close_barrier(self, parking_id: int, *, simulate_unreachable: bool = False) -> CommandResultOut:
        req = {"simulate_unreachable": simulate_unreachable}
        if simulate_unreachable:
            event = await self._append_event(
                parking_id=parking_id,
                device_kind=KIND_BARRIER,
                action="barrier_close",
                request_payload=req,
                response_payload=None,
                success=False,
                error_message="Эмулятор: устройство недоступно (тестовый режим)",
            )
            await self._publish_device_event(event, event_type=EventType.DEVICE_UNAVAILABLE.value, message="device unavailable")
            st = await self._get_device_row(parking_id, KIND_BARRIER)
            cur = st.state if st else _default_barrier_state()
            return CommandResultOut(
                success=False,
                parking_id=parking_id,
                device_kind=KIND_BARRIER,
                action="barrier_close",
                state=cur,
                message="Устройство недоступно (симуляция)",
            )
        new_state = {"position": "closed"}
        await self._upsert_state(parking_id, KIND_BARRIER, new_state)
        event = await self._append_event(
            parking_id=parking_id,
            device_kind=KIND_BARRIER,
            action="barrier_close",
            request_payload=req,
            response_payload=new_state,
            success=True,
            error_message=None,
        )
        await self._publish_device_event(event, event_type=EventType.BARRIER_CLOSED.value, message="barrier closed")
        return CommandResultOut(
            success=True,
            parking_id=parking_id,
            device_kind=KIND_BARRIER,
            action="barrier_close",
            state=new_state,
            message=None,
        )

    async def set_lighting(self, parking_id: int, body: LightingSetBody) -> CommandResultOut:
        req = body.model_dump()
        if body.simulate_unreachable:
            event = await self._append_event(
                parking_id=parking_id,
                device_kind=KIND_LIGHTING,
                action="lighting_set",
                request_payload=req,
                response_payload=None,
                success=False,
                error_message="Эмулятор: устройство недоступно (тестовый режим)",
            )
            await self._publish_device_event(event, event_type=EventType.DEVICE_UNAVAILABLE.value, message="device unavailable")
            st = await self._get_device_row(parking_id, KIND_LIGHTING)
            cur = st.state if st else _default_lighting_state()
            return CommandResultOut(
                success=False,
                parking_id=parking_id,
                device_kind=KIND_LIGHTING,
                action="lighting_set",
                state=cur,
                message="Устройство недоступно (симуляция)",
            )
        new_state = {"on": body.on, "brightness": body.brightness if body.on else 0}
        await self._upsert_state(parking_id, KIND_LIGHTING, new_state)
        event = await self._append_event(
            parking_id=parking_id,
            device_kind=KIND_LIGHTING,
            action="lighting_set",
            request_payload=req,
            response_payload=new_state,
            success=True,
            error_message=None,
        )
        await self._publish_device_event(event, event_type=EventType.LIGHTING_CHANGED.value, message="lighting changed")
        return CommandResultOut(
            success=True,
            parking_id=parking_id,
            device_kind=KIND_LIGHTING,
            action="lighting_set",
            state=new_state,
            message=None,
        )

    async def list_events(
        self,
        parking_id: int,
        *,
        page: int = 1,
        size: int = 50,
    ) -> IntegrationEventListOut:
        offset = (page - 1) * size
        count_stmt = select(func.count(IntegrationDeviceEvent.id)).where(
            IntegrationDeviceEvent.parking_id == parking_id
        )
        stmt = (
            select(IntegrationDeviceEvent)
            .where(IntegrationDeviceEvent.parking_id == parking_id)
            .order_by(IntegrationDeviceEvent.created_at.desc())
            .offset(offset)
            .limit(size)
        )
        total = (await self._session.execute(count_stmt)).scalar_one()
        rows = (await self._session.execute(stmt)).scalars().all()
        items = [
            IntegrationEventOut(
                id=r.id,
                parking_id=r.parking_id,
                device_kind=r.device_kind,
                action=r.action,
                success=r.success,
                error_message=r.error_message,
                request_payload=r.request_payload,
                response_payload=r.response_payload,
                created_at=r.created_at,
            )
            for r in rows
        ]
        return IntegrationEventListOut(items=items, total=int(total), page=page, size=size)
