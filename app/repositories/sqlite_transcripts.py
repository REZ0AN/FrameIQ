import json
from datetime import UTC, datetime
from pathlib import Path
from sqlite3 import Row
from uuid import uuid4

from app.models.transcript import (
    NewTranscript,
    TranscriptRecord,
    TranscriptSegment,
    TranscriptSummary,
)
from app.repositories.database import connect


class SQLiteTranscriptRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    async def get_by_hash(self, url_hash: str) -> TranscriptRecord | None:
        async with connect(self._database_path) as connection:
            cursor = await connection.execute(
                "SELECT * FROM transcripts WHERE url_hash = ?",
                (url_hash,),
            )
            row = await cursor.fetchone()
        return _to_record(row) if row else None

    async def get_by_id(self, transcript_id: str) -> TranscriptRecord | None:
        async with connect(self._database_path) as connection:
            cursor = await connection.execute(
                "SELECT * FROM transcripts WHERE id = ?",
                (transcript_id,),
            )
            row = await cursor.fetchone()
        return _to_record(row) if row else None

    async def list_recent(self, limit: int) -> list[TranscriptSummary]:
        async with connect(self._database_path) as connection:
            cursor = await connection.execute(
                """
                SELECT
                    transcripts.id,
                    transcripts.canonical_url,
                    transcripts.video_id,
                    transcripts.title,
                    transcripts.language,
                    transcripts.provider,
                    transcripts.created_at,
                    (
                        SELECT run_items.run_id
                        FROM run_items
                        JOIN analysis_runs ON analysis_runs.id = run_items.run_id
                        WHERE run_items.transcript_id = transcripts.id
                        ORDER BY analysis_runs.created_at DESC
                        LIMIT 1
                    ) AS latest_run_id
                FROM transcripts
                ORDER BY transcripts.created_at DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = await cursor.fetchall()
        return [_to_summary(row) for row in rows]

    async def create_or_get(self, transcript: NewTranscript) -> TranscriptRecord:
        transcript_id = str(uuid4())
        created_at = datetime.now(UTC).isoformat()
        segments_json = json.dumps(
            [segment.model_dump() for segment in transcript.segments],
            ensure_ascii=False,
        )
        async with connect(self._database_path) as connection:
            await connection.execute(
                """
                INSERT OR IGNORE INTO transcripts (
                    id, source_url, canonical_url, url_hash, video_id, title,
                    language, provider, transcript_text, segments_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    transcript_id,
                    transcript.source_url,
                    transcript.canonical_url,
                    transcript.url_hash,
                    transcript.video_id,
                    transcript.title,
                    transcript.language,
                    transcript.provider,
                    transcript.text,
                    segments_json,
                    created_at,
                ),
            )
            await connection.commit()
        record = await self.get_by_hash(transcript.url_hash)
        if record is None:
            raise RuntimeError("Transcript could not be persisted.")
        return record


def _to_record(row: Row) -> TranscriptRecord:
    return TranscriptRecord(
        id=row["id"],
        source_url=row["source_url"],
        canonical_url=row["canonical_url"],
        url_hash=row["url_hash"],
        video_id=row["video_id"],
        title=row["title"],
        language=row["language"],
        provider=row["provider"],
        text=row["transcript_text"],
        segments=[
            TranscriptSegment.model_validate(segment)
            for segment in json.loads(row["segments_json"])
        ],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def _to_summary(row: Row) -> TranscriptSummary:
    return TranscriptSummary(
        id=row["id"],
        canonical_url=row["canonical_url"],
        video_id=row["video_id"],
        title=row["title"],
        language=row["language"],
        provider=row["provider"],
        created_at=datetime.fromisoformat(row["created_at"]),
        latest_run_id=row["latest_run_id"],
    )
