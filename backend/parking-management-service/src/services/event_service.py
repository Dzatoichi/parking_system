from src.dao.event_dao import EventDAO
from src.schemas import PaginatedResponse
from src.schemas.events_schemas import SystemEventReadSchema, SystemEventCreateSchema
from src.services.system_event_ws import system_event_ws_manager


class EventService:
    def __init__(
        self,
        event_dao: EventDAO
    ) -> None:
        self._dao = event_dao

    async def get_by_id(self, event_id: int) -> SystemEventReadSchema | None:
        event = await self._dao.get_by_id(event_id)
        return SystemEventReadSchema.model_validate(event)

    async def get_all_paginated(
        self,
        parking_id: int,
        page: int = 1,
        size: int = 50,
    ) -> PaginatedResponse[SystemEventReadSchema] | None:
        events, total = await self._dao.get_all_paginated_by_parking(
            parking_id=parking_id,
            page=page,
            size=size,
        )
        items = [SystemEventReadSchema.model_validate(event) for event in events]
        return PaginatedResponse.create(
            items=items,
            total=total,
            page=page,
            size=size
        )

    async def add_event(
            self,
        data: SystemEventCreateSchema,
    ) -> SystemEventReadSchema:
        data_dict = data.model_dump()
        event = await self._dao.create(data_dict)
        await system_event_ws_manager.broadcast_event(event)
        return SystemEventReadSchema.model_validate(event)
