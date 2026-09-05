from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.dependencies import get_health_service
from app.models.health import HealthResponse
from app.services.health import HealthService


router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse}},
)
async def health_check(
    health: Annotated[HealthService, Depends(get_health_service)],
) -> HealthResponse | JSONResponse:
    if not await health.database_is_available():
        response = HealthResponse(status="unavailable", database="unavailable")
        return JSONResponse(status_code=503, content=response.model_dump())
    return HealthResponse(status="ok", database="ok")
