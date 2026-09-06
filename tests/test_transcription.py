from collections.abc import Sequence
from pathlib import Path

import pytest

from app.models.run import NewRunItem
from app.models.transcript import FetchedTranscript, TranscriptSegment
from app.repositories.database import initialize_database
from app.repositories.sqlite_runs import SQLiteRunRepository
from app.repositories.sqlite_transcripts import SQLiteTranscriptRepository
from app.services.transcription import TranscriptionService
from app.services.url_normalizer import NormalizedYouTubeUrl, normalize_youtube_url


class CountingProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def fetch(
        self,
        video: NormalizedYouTubeUrl,
        languages: Sequence[str],
    ) -> FetchedTranscript:
        self.calls += 1
        return FetchedTranscript(
            title=video.video_id,
            language=languages[0],
            provider="counting",
            segments=[TranscriptSegment(start=0, duration=1, text="cached text")],
        )


@pytest.mark.asyncio
async def test_second_run_uses_cache_without_provider_call(tmp_path: Path) -> None:
    database = tmp_path / "cache.sqlite3"
    await initialize_database(database)
    runs = SQLiteRunRepository(database)
    transcripts = SQLiteTranscriptRepository(database)
    provider = CountingProvider()
    service = TranscriptionService(transcripts, runs, provider, ["en", "hi", "bn"], 3)
    normalized = normalize_youtube_url("dQw4w9WgXcQ")

    for index in range(2):
        run_id = f"00000000-0000-4000-8000-00000000000{index}"
        await runs.create(
            run_id,
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
        outcome = await service.transcribe_run(run_id)
        assert len(outcome.transcripts) == 1
        assert outcome.transcripts[0].cached is (index == 1)

    assert provider.calls == 1
