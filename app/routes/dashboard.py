from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.dependencies import get_dashboard_service
from app.services.dashboard import DashboardService


router = APIRouter()


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    dashboard: Annotated[DashboardService, Depends(get_dashboard_service)],
) -> HTMLResponse:
    view = await dashboard.get()
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "view": view,
            "deleted": request.query_params.get("deleted") == "1",
        },
    )
