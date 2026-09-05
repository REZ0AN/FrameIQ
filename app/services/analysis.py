import asyncio
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol, TypeVar

from openai import AsyncOpenAI
from pydantic import BaseModel

from app.models.analysis import (
    BatchSynthesis,
    ChunkAnalysis,
    VideoAnalysis,
)
from app.models.transcript import TranscriptRecord


class AnalysisService(Protocol):
    async def analyze_videos(
        self,
        transcripts: Sequence[TranscriptRecord],
    ) -> list[VideoAnalysis]: ...

    async def synthesize(
        self,
        analyses: Sequence[VideoAnalysis],
    ) -> BatchSynthesis: ...


SchemaT = TypeVar("SchemaT", bound=BaseModel)


class OpenAICompatibleAnalysisService:
    def __init__(
        self,
        api_key: str | None,
        model: str,
        base_url: str | None,
        prompt_path: Path,
        concurrency: int,
        chunk_characters: int,
    ) -> None:
        if api_key and base_url:
            self._client = AsyncOpenAI(
                api_key=api_key,
                base_url=base_url,
                max_retries=0,
            )
        elif api_key:
            self._client = AsyncOpenAI(api_key=api_key, max_retries=0)
        else:
            self._client = None
        self._model = model
        self._instructions = prompt_path.read_text(encoding="utf-8")
        self._semaphore = asyncio.Semaphore(concurrency)
        self._chunk_characters = chunk_characters

    async def analyze_videos(
        self,
        transcripts: Sequence[TranscriptRecord],
    ) -> list[VideoAnalysis]:
        results = await asyncio.gather(
            *(self._analyze_video(transcript) for transcript in transcripts)
        )
        return list(results)

    async def synthesize(
        self,
        analyses: Sequence[VideoAnalysis],
    ) -> BatchSynthesis:
        payload = json.dumps(
            [analysis.model_dump() for analysis in analyses],
            ensure_ascii=False,
        )
        return await self._request(
            BatchSynthesis,
            "Synthesize these video analyses. Compare only the supplied material.\n\n"
            + payload,
        )

    async def _analyze_video(self, transcript: TranscriptRecord) -> VideoAnalysis:
        chunks = _chunk_transcript(transcript, self._chunk_characters)
        if len(chunks) == 1:
            result = await self._request(
                VideoAnalysis,
                _video_request(transcript, chunks[0]),
            )
        else:
            notes = await asyncio.gather(
                *(
                    self._request(
                        ChunkAnalysis,
                        f"Analyze chunk {index + 1} of {len(chunks)} from "
                        f"{transcript.title} ({transcript.video_id}).\n\n{chunk}",
                    )
                    for index, chunk in enumerate(chunks)
                )
            )
            result = await self._request(
                VideoAnalysis,
                "Create the final per-video report from these ordered chunk analyses. "
                "Remove duplication and preserve valid timestamps.\n\n"
                f"Video ID: {transcript.video_id}\nTitle: {transcript.title}\n"
                + json.dumps(
                    [note.model_dump() for note in notes],
                    ensure_ascii=False,
                ),
            )
        return result.model_copy(
            update={"video_id": transcript.video_id, "title": transcript.title}
        )

    async def _request(self, schema: type[SchemaT], content: str) -> SchemaT:
        if self._client is None:
            raise RuntimeError("AI_API_KEY is not configured.")
        async with self._semaphore:
            completion = await self._client.beta.chat.completions.parse(
                model=self._model,
                messages=[
                    {"role": "system", "content": self._instructions},
                    {"role": "user", "content": content},
                ],
                response_format=schema,
            )
        parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise RuntimeError("The analysis model returned no structured output.")
        return schema.model_validate(parsed)


def _video_request(transcript: TranscriptRecord, transcript_text: str) -> str:
    return (
        "Analyze this timestamped YouTube transcript. Do not introduce facts that "
        "are absent from it.\n\n"
        f"Video ID: {transcript.video_id}\n"
        f"Title: {transcript.title}\n"
        f"Language: {transcript.language}\n\n"
        f"{transcript_text}"
    )


def _chunk_transcript(
    transcript: TranscriptRecord,
    character_limit: int,
) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_size = 0
    for segment in transcript.segments:
        line = f"[{_format_time(segment.start)}] {segment.text}"
        if current and current_size + len(line) + 1 > character_limit:
            chunks.append("\n".join(current))
            current = []
            current_size = 0
        current.append(line)
        current_size += len(line) + 1
    if current:
        chunks.append("\n".join(current))
    return chunks or [transcript.text]


def _format_time(seconds: float) -> str:
    total = int(seconds)
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"
