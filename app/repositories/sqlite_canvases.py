from datetime import UTC, datetime
from pathlib import Path
from sqlite3 import Row

from app.models.canvas import CanvasDocument
from app.repositories.database import connect


class SQLiteCanvasRepository:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    async def get(self, run_id: str) -> CanvasDocument | None:
        async with connect(self._database_path) as connection:
            cursor = await connection.execute(
                "SELECT * FROM canvas_documents WHERE run_id = ?",
                (run_id,),
            )
            row = await cursor.fetchone()
        return _to_document(row) if row else None

    async def save(self, run_id: str, markdown_text: str) -> CanvasDocument:
        updated_at = datetime.now(UTC).isoformat()
        async with connect(self._database_path) as connection:
            await connection.execute(
                """
                INSERT INTO canvas_documents (run_id, markdown_text, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    markdown_text = excluded.markdown_text,
                    updated_at = excluded.updated_at
                """,
                (run_id, markdown_text, updated_at),
            )
            await connection.commit()
        document = await self.get(run_id)
        if document is None:
            raise RuntimeError("Canvas document could not be persisted.")
        return document


def _to_document(row: Row) -> CanvasDocument:
    return CanvasDocument(
        run_id=row["run_id"],
        markdown_text=row["markdown_text"],
        updated_at=datetime.fromisoformat(row["updated_at"]),
    )
