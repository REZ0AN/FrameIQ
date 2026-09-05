from pathlib import Path
from typing import Protocol

from app.repositories.database import connect


class HealthService(Protocol):
    async def database_is_available(self) -> bool: ...


class SQLiteHealthService:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    async def database_is_available(self) -> bool:
        try:
            async with connect(self._database_path) as connection:
                cursor = await connection.execute("SELECT 1")
                row = await cursor.fetchone()
        except Exception:
            return False
        return row is not None and row[0] == 1
