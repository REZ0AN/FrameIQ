from typing import Any
from uuid import UUID, uuid4

from app.graph.nodes import report_from_state
from app.models.run import (
    AnalysisRun,
    NewRunItem,
    RunItemStatus,
    RunMode,
    RunStatusEvent,
)
from app.models.web import ResultsView
from app.repositories.protocols import RunRepository, TranscriptRepository
from app.services.url_normalizer import InvalidYouTubeUrl, normalize_youtube_url


class SubmissionError(ValueError):
    pass


class RunService:
    def __init__(
        self,
        runs: RunRepository,
        transcripts: TranscriptRepository,
        graph: Any,
        max_batch_size: int,
    ) -> None:
        self._runs = runs
        self._transcripts = transcripts
        self._graph = graph
        self._max_batch_size = max_batch_size

    async def create(self, input_value: str) -> tuple[AnalysisRun, list[str]]:
        cleaned = input_value.strip()
        mode = RunMode.BATCH if "," in cleaned else RunMode.SINGLE
        tokens = [token.strip() for token in cleaned.split(",") if token.strip()]
        if not tokens:
            raise SubmissionError("Enter at least one YouTube URL.")

        items: list[NewRunItem] = []
        unique_urls: list[str] = []
        seen_hashes: set[str] = set()
        for token in tokens:
            try:
                normalized = normalize_youtube_url(token)
            except InvalidYouTubeUrl as error:
                if mode is RunMode.SINGLE:
                    raise SubmissionError(str(error)) from error
                items.append(
                    NewRunItem(
                        position=len(items),
                        source_url=token,
                        status=RunItemStatus.FAILED,
                        error=str(error),
                    )
                )
                continue
            if normalized.url_hash in seen_hashes:
                continue
            seen_hashes.add(normalized.url_hash)
            unique_urls.append(normalized.canonical_url)
            items.append(
                NewRunItem(
                    position=len(items),
                    source_url=token,
                    canonical_url=normalized.canonical_url,
                    url_hash=normalized.url_hash,
                    video_id=normalized.video_id,
                )
            )

        if len(seen_hashes) > self._max_batch_size:
            raise SubmissionError(
                f"Submit at most {self._max_batch_size} unique YouTube videos."
            )
        if not items:
            raise SubmissionError("Enter at least one valid YouTube URL.")

        run_id = str(uuid4())
        run = await self._runs.create(
            run_id=run_id,
            input_value=cleaned,
            mode=mode.value,
            items=items,
        )
        return run, unique_urls

    async def get_results(self, run_id: str) -> ResultsView | None:
        _validate_run_id(run_id)
        run = await self._runs.get(run_id)
        if run is None:
            return None
        items = await self._runs.list_items(run_id)
        transcript_records = []
        for item in items:
            if item.transcript_id:
                record = await self._transcripts.get_by_id(item.transcript_id)
                if record:
                    transcript_records.append(record)

        report = None
        try:
            snapshot = await self._graph.aget_state(
                {"configurable": {"thread_id": run_id}}
            )
            if snapshot.values:
                candidate = report_from_state(snapshot.values)
                if candidate.videos or candidate.batch_synthesis:
                    report = candidate
        except Exception:
            if run.status in {run.status.COMPLETED, run.status.COMPLETED_WITH_ERRORS}:
                raise

        return ResultsView(
            run=run,
            items=items,
            transcripts=transcript_records,
            report=report,
        )

    async def get_status(self, run_id: str) -> RunStatusEvent | None:
        _validate_run_id(run_id)
        run = await self._runs.get(run_id)
        if run is None:
            return None
        return RunStatusEvent(
            run_id=run.id,
            status=run.status,
            success_count=run.success_count,
            error_count=run.error_count,
            total_count=run.total_count,
            message=_status_message(run),
            terminal=run.status.terminal,
        )


def _validate_run_id(run_id: str) -> None:
    try:
        UUID(run_id)
    except ValueError as error:
        raise SubmissionError("Invalid run ID.") from error


def _status_message(run: AnalysisRun) -> str:
    if run.status is run.status.QUEUED:
        return "Queued for processing"
    if run.status is run.status.RUNNING:
        return f"Processed {run.success_count + run.error_count} of {run.total_count} videos"
    if run.status is run.status.COMPLETED:
        return "Analysis complete"
    if run.status is run.status.COMPLETED_WITH_ERRORS:
        return "Analysis complete with some unavailable videos"
    return run.error or "The run could not be completed"
