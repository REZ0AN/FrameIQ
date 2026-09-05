import asyncio
from datetime import UTC, datetime

from app.repositories.protocols import RunRepository
from app.services.executor import RunExecutor


class ThreadReaper:
    def __init__(
        self,
        runs: RunRepository,
        executor: RunExecutor,
        interval_seconds: float,
    ) -> None:
        self._runs = runs
        self._executor = executor
        self._interval_seconds = interval_seconds
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._loop(), name="thread-reaper")

    async def stop(self) -> None:
        self._stop.set()
        if self._task:
            await self._task
        await self.flush()

    async def flush(self) -> None:
        await self._runs.touch_active(self._executor.active_run_ids, datetime.now(UTC))

    async def _loop(self) -> None:
        while not self._stop.is_set():
            try:
                await asyncio.wait_for(
                    self._stop.wait(),
                    timeout=self._interval_seconds,
                )
            except TimeoutError:
                await self.flush()
