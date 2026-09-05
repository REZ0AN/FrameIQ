from langgraph.checkpoint.base import BaseCheckpointSaver

from app.models.canvas import CanvasDocument
from app.models.run import AnalysisRun
from app.models.web import ResultsView
from app.repositories.protocols import CanvasRepository, RunRepository
from app.services.markdown import MarkdownRenderer


class CanvasNotFound(ValueError):
    pass


class CanvasConflict(ValueError):
    pass


class CanvasService:
    def __init__(
        self,
        runs: RunRepository,
        documents: CanvasRepository,
        checkpoints: BaseCheckpointSaver,
        markdown: MarkdownRenderer,
    ) -> None:
        self._runs = runs
        self._documents = documents
        self._checkpoints = checkpoints
        self._markdown = markdown

    async def get_document(self, run_id: str) -> CanvasDocument | None:
        return await self._documents.get(run_id)

    async def editable_markdown(self, view: ResultsView) -> str:
        document = await self._documents.get(view.run.id)
        if document:
            return document.markdown_text
        return self._markdown.from_report(
            view.report,
            source=view.run.input_value,
            error=view.run.error,
        )

    def render(self, markdown_text: str) -> str:
        return self._markdown.render(markdown_text)

    async def save(self, run_id: str, markdown_text: str) -> CanvasDocument:
        run = await self._require_terminal_run(run_id)
        return await self._documents.save(run.id, markdown_text)

    async def delete(self, run_id: str) -> None:
        run = await self._require_terminal_run(run_id)
        await self._checkpoints.adelete_thread(run.id)
        deleted = await self._runs.delete(run.id)
        if not deleted:
            raise CanvasNotFound("Canvas not found.")

    async def _require_terminal_run(self, run_id: str) -> AnalysisRun:
        run = await self._runs.get(run_id)
        if run is None:
            raise CanvasNotFound("Canvas not found.")
        if not run.status.terminal:
            raise CanvasConflict("Wait for the canvas to finish before changing it.")
        return run
