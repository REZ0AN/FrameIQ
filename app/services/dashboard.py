import asyncio

from app.models.dashboard import DashboardView
from app.repositories.protocols import RunRepository, TranscriptRepository


class DashboardService:
    def __init__(
        self,
        runs: RunRepository,
        transcripts: TranscriptRepository,
        item_limit: int = 50,
    ) -> None:
        self._runs = runs
        self._transcripts = transcripts
        self._item_limit = item_limit

    async def get(self) -> DashboardView:
        runs, transcripts = await asyncio.gather(
            self._runs.list_recent(self._item_limit),
            self._transcripts.list_recent(self._item_limit),
        )
        return DashboardView(runs=runs, transcripts=transcripts)
