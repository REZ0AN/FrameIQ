import asyncio
from collections.abc import Sequence
from typing import Protocol

from app.models.run import RunItem
from app.models.transcript import (
    FetchedTranscript,
    NewTranscript,
    TranscriptRecord,
    TranscriptReference,
    TranscriptionFailure,
    TranscriptionOutcome,
)
from app.repositories.protocols import RunRepository, TranscriptRepository
from app.services.url_normalizer import NormalizedYouTubeUrl


class TranscriptProvider(Protocol):
    async def fetch(
        self,
        video: NormalizedYouTubeUrl,
        languages: Sequence[str],
    ) -> FetchedTranscript: ...


class TranscriptionService:
    def __init__(
        self,
        transcripts: TranscriptRepository,
        runs: RunRepository,
        provider: TranscriptProvider,
        languages: Sequence[str],
        concurrency: int,
    ) -> None:
        self._transcripts = transcripts
        self._runs = runs
        self._provider = provider
        self._languages = tuple(languages)
        self._semaphore = asyncio.Semaphore(concurrency)
        self._hash_locks: dict[str, asyncio.Lock] = {}

    async def transcribe_run(self, run_id: str) -> TranscriptionOutcome:
        items = await self._runs.list_items(run_id)
        candidates = [item for item in items if item.video_id and item.url_hash]
        results = await asyncio.gather(
            *(self._transcribe_item(item) for item in candidates),
            return_exceptions=True,
        )
        outcome = TranscriptionOutcome()
        for item, result in zip(candidates, results, strict=True):
            if isinstance(result, BaseException):
                message = _safe_error(result)
                await self._runs.fail_item(item.id, message)
                outcome.errors.append(
                    TranscriptionFailure(source_url=item.source_url, error=message)
                )
            else:
                record, cached = result
                await self._runs.complete_item(item.id, record.id)
                outcome.transcripts.append(
                    TranscriptReference(
                        transcript_id=record.id,
                        source_url=item.source_url,
                        canonical_url=record.canonical_url,
                        video_id=record.video_id,
                        title=record.title,
                        cached=cached,
                    )
                )
        for item in items:
            if item.status.value == "failed":
                outcome.errors.append(
                    TranscriptionFailure(
                        source_url=item.source_url,
                        error=item.error or "Invalid YouTube URL.",
                    )
                )
        return outcome

    async def _transcribe_item(self, item: RunItem) -> tuple[TranscriptRecord, bool]:
        if not item.video_id or not item.url_hash or not item.canonical_url:
            raise ValueError("Run item was not normalized.")
        cached = await self._transcripts.get_by_hash(item.url_hash)
        if cached:
            return cached, True

        lock = self._hash_locks.setdefault(item.url_hash, asyncio.Lock())
        async with lock:
            cached = await self._transcripts.get_by_hash(item.url_hash)
            if cached:
                return cached, True
            async with self._semaphore:
                fetched = await self._provider.fetch(
                    NormalizedYouTubeUrl(
                        source_url=item.source_url,
                        canonical_url=item.canonical_url,
                        url_hash=item.url_hash,
                        video_id=item.video_id,
                    ),
                    self._languages,
                )
            record = await self._transcripts.create_or_get(
                NewTranscript(
                    source_url=item.source_url,
                    canonical_url=item.canonical_url,
                    url_hash=item.url_hash,
                    video_id=item.video_id,
                    title=fetched.title,
                    language=fetched.language,
                    provider=fetched.provider,
                    text=" ".join(segment.text for segment in fetched.segments),
                    segments=fetched.segments,
                )
            )
            return record, False


def _safe_error(error: BaseException) -> str:
    message = str(error).strip()
    return message[:500] if message else error.__class__.__name__
