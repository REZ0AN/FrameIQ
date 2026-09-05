from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError

from app.dependencies import get_canvas_service, get_run_service
from app.models.canvas import CanvasUpdate
from app.models.web import ResultsView
from app.services.canvases import CanvasConflict, CanvasNotFound, CanvasService
from app.services.runs import RunService, SubmissionError


router = APIRouter()


@router.get("/runs/{run_id}/edit", response_class=HTMLResponse)
async def edit_canvas_page(
    run_id: str,
    request: Request,
    runs: Annotated[RunService, Depends(get_run_service)],
    canvases: Annotated[CanvasService, Depends(get_canvas_service)],
) -> HTMLResponse:
    view = await _get_terminal_view(run_id, runs)
    markdown_text = await canvases.editable_markdown(view)
    return _editor_response(
        request=request,
        view=view,
        canvases=canvases,
        markdown_text=markdown_text,
    )


@router.post("/runs/{run_id}/preview", response_class=HTMLResponse)
async def preview_canvas(
    run_id: str,
    request: Request,
    markdown_text: Annotated[str, Form()],
    runs: Annotated[RunService, Depends(get_run_service)],
    canvases: Annotated[CanvasService, Depends(get_canvas_service)],
) -> HTMLResponse:
    view = await _get_terminal_view(run_id, runs)
    error = _validation_error(markdown_text)
    return _editor_response(
        request=request,
        view=view,
        canvases=canvases,
        markdown_text=markdown_text,
        error=error,
        status_code=422 if error else 200,
    )


@router.post("/runs/{run_id}/content")
async def update_canvas(
    run_id: str,
    markdown_text: Annotated[str, Form()],
    runs: Annotated[RunService, Depends(get_run_service)],
    canvases: Annotated[CanvasService, Depends(get_canvas_service)],
    request: Request,
) -> HTMLResponse:
    view = await _get_terminal_view(run_id, runs)
    error = _validation_error(markdown_text)
    if error:
        return _editor_response(
            request=request,
            view=view,
            canvases=canvases,
            markdown_text=markdown_text,
            error=error,
            status_code=422,
        )
    try:
        await canvases.save(run_id, markdown_text)
    except CanvasNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CanvasConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return RedirectResponse(url=f"/runs/{run_id}?updated=1", status_code=303)


@router.post("/runs/{run_id}/delete")
async def delete_canvas(
    run_id: str,
    canvases: Annotated[CanvasService, Depends(get_canvas_service)],
) -> RedirectResponse:
    try:
        await canvases.delete(run_id)
    except CanvasNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CanvasConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return RedirectResponse(url="/dashboard?deleted=1", status_code=303)


async def _get_terminal_view(run_id: str, runs: RunService) -> ResultsView:
    try:
        view = await runs.get_results(run_id)
    except SubmissionError as exc:
        raise HTTPException(status_code=404, detail="Canvas not found.") from exc
    if view is None:
        raise HTTPException(status_code=404, detail="Canvas not found.")
    if not view.run.status.terminal:
        raise HTTPException(
            status_code=409,
            detail="Wait for the canvas to finish before changing it.",
        )
    return view


def _validation_error(markdown_text: str) -> str | None:
    try:
        CanvasUpdate(markdown_text=markdown_text)
    except ValidationError as exc:
        return str(exc.errors()[0]["msg"])
    return None


def _editor_response(
    request: Request,
    view: ResultsView,
    canvases: CanvasService,
    markdown_text: str,
    error: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="canvas_editor.html",
        context={
            "view": view,
            "markdown_text": markdown_text,
            "preview_html": canvases.render(markdown_text),
            "error": error,
        },
        status_code=status_code,
    )
