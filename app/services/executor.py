import asyncio
from collections.abc import Sequence
from typing import Any

from langchain_core.messages import HumanMessage

from app.models.run import RunStatus
from app.repositories.protocols import RunRepository


class RunExecutor:
    def __init__(self, graph: Any, runs: RunRepository) -> None:
        self._graph = graph
        self._runs = runs
        self._tasks: dict[str, asyncio.Task[None]] = {}

    @property
    def active_run_ids(self) -> set[str]:
        return set(self._tasks)

    def start(self, run_id: str, urls: Sequence[str]) -> None:
        if run_id in self._tasks:
            return
        task = asyncio.create_task(
            self._execute(run_id, list(urls)),
            name=f"analysis-run-{run_id}",
        )
        self._tasks[run_id] = task
        task.add_done_callback(lambda _: self._tasks.pop(run_id, None))

    async def _execute(self, run_id: str, urls: list[str]) -> None:
        await self._runs.set_status(run_id, RunStatus.RUNNING)
        try:
            result = await self._graph.ainvoke(
                {
                    "run_id": run_id,
                    "urls": urls,
                    "messages": [
                        HumanMessage(
                            content="Analyze these YouTube videos: " + ", ".join(urls)
                        )
                    ],
                },
                {"configurable": {"thread_id": run_id}},
            )
            analyses = result.get("video_analyses", [])
            errors = result.get("transcription_errors", [])
            if not analyses:
                message = (
                    errors[0].get("error", "No transcript could be analyzed.")
                    if errors
                    else "No transcript could be analyzed."
                )
                await self._runs.set_status(run_id, RunStatus.FAILED, message)
            elif errors:
                await self._runs.set_status(run_id, RunStatus.COMPLETED_WITH_ERRORS)
            else:
                await self._runs.set_status(run_id, RunStatus.COMPLETED)
        except asyncio.CancelledError:
            await self._runs.set_status(
                run_id,
                RunStatus.INTERRUPTED,
                "The application stopped before this run completed.",
            )
            raise
        except Exception as error:
            message = str(error).strip()[:500] or error.__class__.__name__
            await self._runs.set_status(run_id, RunStatus.FAILED, message)

    async def shutdown(self) -> None:
        tasks = list(self._tasks.values())
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
