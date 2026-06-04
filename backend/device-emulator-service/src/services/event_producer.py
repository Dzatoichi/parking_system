from src.schemas import SystemEventCreateSchema
from src.clients.events_client import EventsClient


class EventProducer:
    def __init__(self, events_client: EventsClient):
        self.events_client = events_client

    async def send_device_event(self, data: SystemEventCreateSchema):
       return await self.events_client.send_device_event(data)
