import asyncio
import time
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.dependencies import get_run_service
from app.models.run import RunStatusEvent
from app.services.runs import RunService, SubmissionError


router = APIRouter()


@router.get("/runs/{run_id}/events")
async def run_events(
    run_id: str,
    request: Request,
    runs: Annotated[RunService, Depends(get_run_service)],
) -> StreamingResponse:
    try:
        initial = await runs.get_status(run_id)
    except SubmissionError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    if initial is None:
        raise HTTPException(status_code=404, detail="Run not found.")
    poll_seconds = request.app.state.container.settings.sse_poll_seconds
    return StreamingResponse(
        _event_stream(request, runs, initial, poll_seconds),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _event_stream(
    request: Request,
    runs: RunService,
    initial: RunStatusEvent,
    poll_seconds: float,
) -> AsyncIterator[str]:
    event = initial
    last_payload = ""
    last_emit = 0.0
    while True:
        payload = event.model_dump_json()
        now = time.monotonic()
        if payload != last_payload:
            yield f"event: status\ndata: {payload}\n\n"
            last_payload = payload
            last_emit = now
        elif now - last_emit >= 15:
            yield ": keep-alive\n\n"
            last_emit = now
        if event.terminal or await request.is_disconnected():
            return
        await asyncio.sleep(poll_seconds)
        refreshed = await runs.get_status(event.run_id)
        if refreshed is None:
            return
        event = refreshed
