from fastapi import APIRouter


health_router = APIRouter(tags=["health"])


@health_router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "payment-service"}
