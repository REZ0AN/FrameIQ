from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite


SCHEMA = """
CREATE TABLE IF NOT EXISTS transcripts (
    id TEXT PRIMARY KEY,
    source_url TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    url_hash TEXT NOT NULL UNIQUE,
    video_id TEXT NOT NULL,
    title TEXT NOT NULL,
    language TEXT NOT NULL,
    provider TEXT NOT NULL,
    transcript_text TEXT NOT NULL,
    segments_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analysis_runs (
    id TEXT PRIMARY KEY,
    input_value TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('single', 'batch')),
    status TEXT NOT NULL,
    total_count INTEGER NOT NULL,
    success_count INTEGER NOT NULL DEFAULT 0,
    error_count INTEGER NOT NULL DEFAULT 0,
    error TEXT,
    heartbeat_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS run_items (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES analysis_runs(id) ON DELETE CASCADE,
    position INTEGER NOT NULL,
    source_url TEXT NOT NULL,
    canonical_url TEXT,
    url_hash TEXT,
    video_id TEXT,
    transcript_id TEXT REFERENCES transcripts(id),
    status TEXT NOT NULL,
    error TEXT,
    UNIQUE(run_id, position)
);

CREATE TABLE IF NOT EXISTS canvas_documents (
    run_id TEXT PRIMARY KEY REFERENCES analysis_runs(id) ON DELETE CASCADE,
    markdown_text TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_run_items_run_id ON run_items(run_id, position);
CREATE INDEX IF NOT EXISTS idx_run_items_hash ON run_items(url_hash);
"""


async def initialize_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    async with connect(path) as connection:
        await connection.execute("PRAGMA journal_mode=WAL")
        await connection.executescript(SCHEMA)
        await connection.commit()


@asynccontextmanager
async def connect(path: Path) -> AsyncIterator[aiosqlite.Connection]:
    connection = await aiosqlite.connect(path)
    connection.row_factory = aiosqlite.Row
    await connection.execute("PRAGMA foreign_keys=ON")
    await connection.execute("PRAGMA busy_timeout=5000")
    try:
        yield connection
    finally:
        await connection.close()
