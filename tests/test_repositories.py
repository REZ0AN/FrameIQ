import asyncio
from datetime import datetime
from pathlib import Path

import pytest

from app.models.run import NewRunItem, RunStatus
from app.models.transcript import NewTranscript, TranscriptSegment
from app.repositories.database import initialize_database
from app.repositories.sqlite_canvases import SQLiteCanvasRepository
from app.repositories.sqlite_runs import SQLiteRunRepository
from app.repositories.sqlite_transcripts import SQLiteTranscriptRepository
from app.services.url_normalizer import normalize_youtube_url
from app.services.reaper import ThreadReaper


@pytest.mark.asyncio
async def test_transcript_deduplication_and_run_counts(tmp_path: Path) -> None:
    database = tmp_path / "repository.sqlite3"
    await initialize_database(database)
    runs = SQLiteRunRepository(database)
    transcripts = SQLiteTranscriptRepository(database)
    canvases = SQLiteCanvasRepository(database)
    normalized = normalize_youtube_url("dQw4w9WgXcQ")
    run = await runs.create(
        "6d51ca15-0324-4fd0-b9a1-b960f4c2427d",
        normalized.source_url,
        "single",
        [
            NewRunItem(
                position=0,
                source_url=normalized.source_url,
                canonical_url=normalized.canonical_url,
                url_hash=normalized.url_hash,
                video_id=normalized.video_id,
            )
        ],
    )
    new = NewTranscript(
        source_url=normalized.source_url,
        canonical_url=normalized.canonical_url,
        url_hash=normalized.url_hash,
        video_id=normalized.video_id,
        title="Test video",
        language="en",
        provider="fake",
        text="hello",
        segments=[TranscriptSegment(start=0, duration=1, text="hello")],
    )
    first = await transcripts.create_or_get(new)
    second = await transcripts.create_or_get(new)
    assert first.id == second.id

    item = (await runs.list_items(run.id))[0]
    await runs.complete_item(item.id, first.id)
    await runs.set_status(run.id, RunStatus.COMPLETED)
    refreshed = await runs.get(run.id)
    assert refreshed is not None
    assert refreshed.success_count == 1
    assert refreshed.error_count == 0
    assert refreshed.status is RunStatus.COMPLETED

    recent_runs = await runs.list_recent(limit=10)
    assert [recent.id for recent in recent_runs] == [run.id]

    recent_transcripts = await transcripts.list_recent(limit=10)
    assert len(recent_transcripts) == 1
    assert recent_transcripts[0].id == first.id
    assert recent_transcripts[0].latest_run_id == run.id

    document = await canvases.save(run.id, "# Edited canvas")
    assert document.markdown_text == "# Edited canvas"

    second_run = await runs.create(
        "cc95ac00-fef2-4e93-b3ee-b8fc1b6a0742",
        normalized.canonical_url,
        "single",
        [
            NewRunItem(
                position=0,
                source_url=normalized.canonical_url,
                canonical_url=normalized.canonical_url,
                url_hash=normalized.url_hash,
                video_id=normalized.video_id,
            )
        ],
    )
    second_item = (await runs.list_items(second_run.id))[0]
    await runs.complete_item(second_item.id, first.id)
    await runs.set_status(second_run.id, RunStatus.COMPLETED)

    assert await runs.delete(run.id) is True
    assert await canvases.get(run.id) is None
    assert await transcripts.get_by_id(first.id) is not None

    assert await runs.delete(second_run.id) is True
    assert await transcripts.get_by_id(first.id) is None


@pytest.mark.asyncio
async def test_reaper_persists_active_run_heartbeats() -> None:
    class HeartbeatRepository:
        def __init__(self) -> None:
            self.calls: list[tuple[set[str], datetime]] = []

        async def touch_active(self, run_ids: set[str], at: datetime) -> None:
            self.calls.append((run_ids, at))

    class ActiveExecutor:
        active_run_ids = {"active-run"}

    repository = HeartbeatRepository()
    reaper = ThreadReaper(repository, ActiveExecutor(), interval_seconds=0.01)  # type: ignore[arg-type]
    reaper.start()
    await asyncio.sleep(0.025)
    await reaper.stop()

    assert repository.calls
    assert repository.calls[-1][0] == {"active-run"}
