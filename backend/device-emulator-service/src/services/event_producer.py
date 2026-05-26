from src.schemas.events_schemas import SystemEventCreateSchema
from src.utils.dependencies import EventsClientDep


class EventProducer:
    def __init__(self, events_client: EventsClientDep):
        self.events_client = events_client

    async def send_device_event(self, data: SystemEventCreateSchema):
       return await self.events_client.send_device_event(data)