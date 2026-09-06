from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from app.dependencies import get_canvas_service, get_run_service
from app.services.canvases import CanvasService
from app.services.runs import RunService, SubmissionError


router = APIRouter()


@router.get("/runs/{run_id}", response_class=HTMLResponse)
async def results_page(
    run_id: str,
    request: Request,
    runs: Annotated[RunService, Depends(get_run_service)],
    canvases: Annotated[CanvasService, Depends(get_canvas_service)],
) -> HTMLResponse:
    try:
        view = await runs.get_results(run_id)
    except SubmissionError:
        view = None
    if view is None:
        return request.app.state.templates.TemplateResponse(
            request=request,
            name="results.html",
            context={
                "view": None,
                "report": None,
                "status": "missing",
                "canvas_html": None,
                "canvas_updated_at": None,
                "updated": False,
            },
            status_code=404,
        )
    document = await canvases.get_document(view.run.id)
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="results.html",
        context={
            "view": view,
            "report": view.report,
            "status": view.run.status.value,
            "canvas_html": (
                canvases.render(document.markdown_text) if document else None
            ),
            "canvas_updated_at": document.updated_at if document else None,
            "updated": request.query_params.get("updated") == "1",
        },
    )
