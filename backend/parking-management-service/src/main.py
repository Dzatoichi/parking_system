from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.routers.booking_router import booking_router
from src.routers.spot_router import spot_router
from src.routers.parking_router import parking_router
from src.routers.camera_router import camera_router
from src.routers.vehicle_router import vehicle_router
from src.routers.health_router import health_router
from src.routers.analytics_router import analytics_router
from src.database.seed import seed_demo_data

@asynccontextmanager
async def lifespan(app: FastAPI):
    await seed_demo_data()
    yield

app = FastAPI(title="Parking Management Service", lifespan=lifespan)

app.include_router(spot_router)
app.include_router(parking_router)
app.include_router(camera_router)
app.include_router(vehicle_router)
app.include_router(health_router)
app.include_router(analytics_router)
app.include_router(booking_router)



