from fastapi import FastAPI
from src.routers.spot_router import spot_router
from src.routers.parking_router import parking_router
from src.routers.camera_router import camera_router
from src.routers.vehicle_router import vehicle_router
from src.routers.health_router import health_router

app = FastAPI(title="Parking Management Service")

app.include_router(spot_router)
app.include_router(parking_router)
app.include_router(camera_router)
app.include_router(vehicle_router)
app.include_router(health_router)