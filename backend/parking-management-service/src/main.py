import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from src.brokers.rabbitmq import BookingEventBroker, CVEventBroker
from src.clients.auth_client import AuthServiceClient
from src.dao.booking_dao import BookingDAO
from src.dao.booking_projection_dao import BookingProjectionDAO
from src.routers.booking_router import booking_router
from src.routers.events_router import events_router
from src.routers.mobile_compat_router import mobile_compat_router
from src.routers.spot_router import spot_router
from src.routers.parking_router import parking_router
from src.routers.camera_router import camera_router
from src.routers.vehicle_router import vehicle_router
from src.routers.health_router import health_router
from src.routers.internal_cv_router import internal_cv_router
from src.routers.analytics_router import analytics_router
from src.database.seed import seed_demo_data
from src.services.booking_projection_service import BookingProjectionService
from src.services.cv_event_service import CVEventService

@asynccontextmanager
async def lifespan(app: FastAPI):
    await seed_demo_data()
    broker = BookingEventBroker()
    cv_broker = CVEventBroker()
    projection_service = BookingProjectionService(
        projection_dao=BookingProjectionDAO(),
        booking_dao=BookingDAO(),
        auth_client=AuthServiceClient(),
    )
    cv_event_service = CVEventService()
    await projection_service.rebuild_projection()
    consumer_task = asyncio.create_task(broker.consume(projection_service.apply_event))
    cv_consumer_task = asyncio.create_task(cv_broker.consume(cv_event_service.apply_event))
    yield
    consumer_task.cancel()
    cv_consumer_task.cancel()
    with suppress(asyncio.CancelledError):
        await consumer_task
    with suppress(asyncio.CancelledError):
        await cv_consumer_task
    await broker.close()
    await cv_broker.close()

app = FastAPI(title="Parking Management Service", lifespan=lifespan)

app.include_router(spot_router)
app.include_router(parking_router)
app.include_router(camera_router)
app.include_router(vehicle_router)
app.include_router(health_router)
app.include_router(analytics_router)
app.include_router(booking_router)
app.include_router(mobile_compat_router)
app.include_router(events_router)
app.include_router(internal_cv_router)


