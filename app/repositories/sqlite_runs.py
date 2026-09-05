from datetime import UTC, datetime
from pathlib import Path
from sqlite3 import Row
from uuid import uuid4

from app.models.run import (
    AnalysisRun,
    NewRunItem,
    RunItem,
    RunItemStatus,
    RunMode,
    RunStatus,
)
from app.repositories.database import connect


class SQLiteRunRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    async def create(
        self,
        run_id: str,
        input_value: str,
        mode: str,
        items: list[NewRunItem],
    ) -> AnalysisRun:
        now = datetime.now(UTC).isoformat()
        async with connect(self._database_path) as connection:
            await connection.execute(
                """
                INSERT INTO analysis_runs (
                    id, input_value, mode, status, total_count, success_count,
                    error_count, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?)
                """,
                (
                    run_id,
                    input_value,
                    mode,
                    RunStatus.QUEUED.value,
                    len(items),
                    sum(item.status is RunItemStatus.FAILED for item in items),
                    now,
                    now,
                ),
            )
            await connection.executemany(
                """
                INSERT INTO run_items (
                    id, run_id, position, source_url, canonical_url, url_hash,
                    video_id, status, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        str(uuid4()),
                        run_id,
                        item.position,
                        item.source_url,
                        item.canonical_url,
                        item.url_hash,
                        item.video_id,
                        item.status.value,
                        item.error,
                    )
                    for item in items
                ],
            )
            await connection.commit()
        run = await self.get(run_id)
        if run is None:
            raise RuntimeError("Run could not be persisted.")
        return run

    async def get(self, run_id: str) -> AnalysisRun | None:
        async with connect(self._database_path) as connection:
            cursor = await connection.execute(
                "SELECT * FROM analysis_runs WHERE id = ?",
                (run_id,),
            )
            row = await cursor.fetchone()
        return _to_run(row) if row else None

    async def list_recent(self, limit: int) -> list[AnalysisRun]:
        async with connect(self._database_path) as connection:
            cursor = await connection.execute(
                "SELECT * FROM analysis_runs ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            rows = await cursor.fetchall()
        return [_to_run(row) for row in rows]

    async def list_items(self, run_id: str) -> list[RunItem]:
        async with connect(self._database_path) as connection:
            cursor = await connection.execute(
                "SELECT * FROM run_items WHERE run_id = ? ORDER BY position",
                (run_id,),
            )
            rows = await cursor.fetchall()
        return [_to_item(row) for row in rows]

    async def complete_item(self, item_id: str, transcript_id: str) -> None:
        await self._finish_item(item_id, RunItemStatus.COMPLETED, transcript_id, None)

    async def fail_item(self, item_id: str, error: str) -> None:
        await self._finish_item(item_id, RunItemStatus.FAILED, None, error)

    async def _finish_item(
        self,
        item_id: str,
        status: RunItemStatus,
        transcript_id: str | None,
        error: str | None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        async with connect(self._database_path) as connection:
            cursor = await connection.execute(
                "SELECT run_id, status FROM run_items WHERE id = ?",
                (item_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                raise KeyError(f"Unknown run item: {item_id}")
            await connection.execute(
                """
                UPDATE run_items
                SET status = ?, transcript_id = ?, error = ?
                WHERE id = ?
                """,
                (status.value, transcript_id, error, item_id),
            )
            await connection.execute(
                """
                UPDATE analysis_runs
                SET success_count = (
                        SELECT COUNT(*) FROM run_items
                        WHERE run_id = ? AND status = 'completed'
                    ),
                    error_count = (
                        SELECT COUNT(*) FROM run_items
                        WHERE run_id = ? AND status = 'failed'
                    ),
                    updated_at = ?
                WHERE id = ?
                """,
                (row["run_id"], row["run_id"], now, row["run_id"]),
            )
            await connection.commit()

    async def set_status(
        self,
        run_id: str,
        status: RunStatus,
        error: str | None = None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        async with connect(self._database_path) as connection:
            await connection.execute(
                """
                UPDATE analysis_runs
                SET status = ?, error = ?, updated_at = ?
                WHERE id = ?
                """,
                (status.value, error, now, run_id),
            )
            await connection.commit()

    async def touch_active(self, run_ids: set[str], at: datetime) -> None:
        if not run_ids:
            return
        placeholders = ",".join("?" for _ in run_ids)
        timestamp = at.isoformat()
        async with connect(self._database_path) as connection:
            await connection.execute(
                f"""
                UPDATE analysis_runs
                SET heartbeat_at = ?, updated_at = ?
                WHERE id IN ({placeholders}) AND status = 'running'
                """,
                (timestamp, timestamp, *sorted(run_ids)),
            )
            await connection.commit()

    async def interrupt_unfinished(self) -> None:
        now = datetime.now(UTC).isoformat()
        async with connect(self._database_path) as connection:
            await connection.execute(
                """
                UPDATE analysis_runs
                SET status = 'interrupted',
                    error = 'The application stopped before this run completed.',
                    updated_at = ?
                WHERE status IN ('queued', 'running')
                """,
                (now,),
            )
            await connection.commit()

    async def delete(self, run_id: str) -> bool:
        async with connect(self._database_path) as connection:
            cursor = await connection.execute(
                "DELETE FROM analysis_runs WHERE id = ?",
                (run_id,),
            )
            await connection.execute(
                """
                DELETE FROM transcripts
                WHERE NOT EXISTS (
                    SELECT 1 FROM run_items
                    WHERE run_items.transcript_id = transcripts.id
                )
                """
            )
            await connection.commit()
        return cursor.rowcount > 0


def _to_run(row: Row) -> AnalysisRun:
    return AnalysisRun(
        id=row["id"],
        input_value=row["input_value"],
        mode=RunMode(row["mode"]),
        status=RunStatus(row["status"]),
        total_count=row["total_count"],
        success_count=row["success_count"],
        error_count=row["error_count"],
        error=row["error"],
        heartbeat_at=(
            datetime.fromisoformat(row["heartbeat_at"])
            if row["heartbeat_at"]
            else None
        ),
        created_at=datetime.fromisoformat(row["created_at"]),
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )


def _to_item(row: Row) -> RunItem:
    return RunItem(
        id=row["id"],
        run_id=row["run_id"],
        position=row["position"],
        source_url=row["source_url"],
        canonical_url=row["canonical_url"],
        url_hash=row["url_hash"],
        video_id=row["video_id"],
        transcript_id=row["transcript_id"],
        status=RunItemStatus(row["status"]),
        error=row["error"],
    )
