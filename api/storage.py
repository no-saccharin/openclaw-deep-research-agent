"""SQLite persistence for research requests."""
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from research.config import Config
from research.schemas import ResearchHistoryItem


def _db_path() -> Path:
    return Path(Config.SQLITE_DB_PATH)


def init_database() -> None:
    db_path = _db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS research_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                conversation_history TEXT NOT NULL DEFAULT '[]',
                requester_type TEXT,
                requester_user_id INTEGER,
                requester_chat_id INTEGER,
                requester_username TEXT,
                success INTEGER NOT NULL,
                result TEXT NOT NULL DEFAULT '',
                sources_count INTEGER NOT NULL DEFAULT 0,
                error TEXT,
                duration_ms INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        existing_columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(research_history)").fetchall()
        }
        required_columns = {
            "requester_type": "ALTER TABLE research_history ADD COLUMN requester_type TEXT",
            "requester_user_id": "ALTER TABLE research_history ADD COLUMN requester_user_id INTEGER",
            "requester_chat_id": "ALTER TABLE research_history ADD COLUMN requester_chat_id INTEGER",
            "requester_username": "ALTER TABLE research_history ADD COLUMN requester_username TEXT",
        }
        for column_name, ddl in required_columns.items():
            if column_name not in existing_columns:
                connection.execute(ddl)
        connection.commit()


def save_research_record(
    *,
    query: str,
    conversation_history: list[dict[str, str]],
    requester_type: str | None,
    requester_user_id: int | None,
    requester_chat_id: int | None,
    requester_username: str | None,
    success: bool,
    result: str,
    sources_count: int,
    error: str | None,
    duration_ms: int,
) -> int:
    created_at = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(_db_path()) as connection:
        cursor = connection.execute(
            """
            INSERT INTO research_history (
                query,
                conversation_history,
                requester_type,
                requester_user_id,
                requester_chat_id,
                requester_username,
                success,
                result,
                sources_count,
                error,
                duration_ms,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                query,
                json.dumps(conversation_history, ensure_ascii=False),
                requester_type,
                requester_user_id,
                requester_chat_id,
                requester_username,
                int(success),
                result,
                sources_count,
                error,
                duration_ms,
                created_at,
            ),
        )
        connection.commit()
        if cursor.lastrowid is None:
            raise RuntimeError("Failed to persist research record")
        return int(cursor.lastrowid)


def list_research_records(
    limit: int = 20,
    requester_user_id: int | None = None,
) -> list[ResearchHistoryItem]:
    safe_limit = max(1, min(limit, 100))
    params: tuple[int, ...] = (safe_limit,)
    where_clause = ""

    if requester_user_id is not None:
        where_clause = "WHERE requester_user_id = ?"
        params = (requester_user_id, safe_limit)

    query = f"""
        SELECT
            id,
            query,
            conversation_history,
            requester_type,
            requester_user_id,
            requester_chat_id,
            requester_username,
            success,
            result,
            sources_count,
            error,
            duration_ms,
            created_at
        FROM research_history
        {where_clause}
        ORDER BY id DESC
        LIMIT ?
    """

    with sqlite3.connect(_db_path()) as connection:
        connection.row_factory = sqlite3.Row
        with closing(
            connection.execute(query, params)
        ) as cursor:
            rows = cursor.fetchall()

    return [
        ResearchHistoryItem(
            id=int(row["id"]),
            query=str(row["query"]),
            conversation_history=json.loads(row["conversation_history"] or "[]"),
            requester_type=row["requester_type"],
            requester_user_id=row["requester_user_id"],
            requester_chat_id=row["requester_chat_id"],
            requester_username=row["requester_username"],
            success=bool(row["success"]),
            result=str(row["result"] or ""),
            sources_count=int(row["sources_count"] or 0),
            error=row["error"],
            duration_ms=int(row["duration_ms"] or 0),
            created_at=str(row["created_at"]),
        )
        for row in rows
    ]