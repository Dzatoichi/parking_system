from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.database.base import init_models
from src.routers.auth_router import auth_router
from src.routers.user_router import user_router
from src.services.bootstrap import bootstrap_defaults
from src.settings.config import settings


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_models()
    await bootstrap_defaults()
    yield


app = FastAPI(
    title=settings.APP_TITLE,
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(user_router)


@app.get("/health", tags=["health"])
async def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
