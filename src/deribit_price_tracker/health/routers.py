from fastapi import APIRouter

from deribit_price_tracker.health.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", summary="Liveness check for container healthchecks")
async def health() -> HealthResponse:
    return HealthResponse()
