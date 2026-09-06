from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError

from app.dependencies import get_run_executor, get_run_service
from app.models.web import AnalyzeSubmission
from app.services.executor import RunExecutor
from app.services.runs import RunService, SubmissionError


router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def input_page(request: Request) -> HTMLResponse:
    return request.app.state.templates.TemplateResponse(
        request=request,
        name="input.html",
        context={"error": None, "value": ""},
    )


@router.post("/runs", response_class=HTMLResponse)
async def create_run(
    request: Request,
    urls: Annotated[str, Form()],
    runs: Annotated[RunService, Depends(get_run_service)],
    executor: Annotated[RunExecutor, Depends(get_run_executor)],
):
    try:
        submission = AnalyzeSubmission(urls=urls)
        run, canonical_urls = await runs.create(submission.urls)
    except (ValidationError, SubmissionError) as error:
        message = _validation_message(error)
        return request.app.state.templates.TemplateResponse(
            request=request,
            name="input.html",
            context={"error": message, "value": urls},
            status_code=422,
        )
    executor.start(run.id, canonical_urls)
    return RedirectResponse(url=f"/runs/{run.id}", status_code=303)


def _validation_message(error: ValidationError | SubmissionError) -> str:
    if isinstance(error, ValidationError):
        return str(error.errors()[0]["msg"]).removeprefix("Value error, ")
    return str(error)
