from datetime import datetime
from typing import Protocol

from app.models.canvas import CanvasDocument
from app.models.run import AnalysisRun, NewRunItem, RunItem, RunStatus
from app.models.transcript import NewTranscript, TranscriptRecord, TranscriptSummary


class TranscriptRepository(Protocol):
    async def get_by_hash(self, url_hash: str) -> TranscriptRecord | None: ...

    async def get_by_id(self, transcript_id: str) -> TranscriptRecord | None: ...

    async def create_or_get(self, transcript: NewTranscript) -> TranscriptRecord: ...

    async def list_recent(self, limit: int) -> list[TranscriptSummary]: ...


class CanvasRepository(Protocol):
    async def get(self, run_id: str) -> CanvasDocument | None: ...

    async def save(self, run_id: str, markdown_text: str) -> CanvasDocument: ...


class RunRepository(Protocol):
    async def create(
        self,
        run_id: str,
        input_value: str,
        mode: str,
        items: list[NewRunItem],
    ) -> AnalysisRun: ...

    async def get(self, run_id: str) -> AnalysisRun | None: ...

    async def list_recent(self, limit: int) -> list[AnalysisRun]: ...

    async def list_items(self, run_id: str) -> list[RunItem]: ...

    async def complete_item(self, item_id: str, transcript_id: str) -> None: ...

    async def fail_item(self, item_id: str, error: str) -> None: ...

    async def set_status(
        self,
        run_id: str,
        status: RunStatus,
        error: str | None = None,
    ) -> None: ...

    async def touch_active(self, run_ids: set[str], at: datetime) -> None: ...

    async def interrupt_unfinished(self) -> None: ...

    async def delete(self, run_id: str) -> bool: ...
