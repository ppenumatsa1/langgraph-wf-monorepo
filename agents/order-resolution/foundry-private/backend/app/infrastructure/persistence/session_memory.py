from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from app.core.database import postgres_db


class SessionMemoryProvider(Protocol):
    def get_messages(self, thread_id: str) -> list[dict[str, Any]]: ...

    def append_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        dedupe_key: str | None = None,
    ) -> None: ...

    def summarize_context(self, thread_id: str, max_messages: int = 8) -> str: ...


class PostgresSessionMemoryStore:
    def __init__(self, _storage_dir: Path | None = None) -> None:
        self._pool = postgres_db.get_pool()

    def get_messages(self, thread_id: str) -> list[dict[str, Any]]:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT role, content
                    FROM conversation_messages
                    WHERE thread_id = %s
                    ORDER BY id ASC
                    """,
                    (thread_id,),
                )
                rows = cur.fetchall()
        return [{"role": row["role"], "content": row["content"]} for row in rows]

    def append_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        dedupe_key: str | None = None,
    ) -> None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO workflow_runs (
                        thread_id, status, input, input_summary,
                        created_at, updated_at, started_at
                    ) VALUES (%s, %s, %s, %s, NOW(), NOW(), NOW())
                    ON CONFLICT (thread_id) DO NOTHING
                    """,
                    (
                        thread_id,
                        "running",
                        content,
                        self._summarize_input(content),
                    ),
                )
                cur.execute(
                    """
                    INSERT INTO conversation_messages (
                        thread_id, role, content, dedupe_key
                    )
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (thread_id, dedupe_key)
                    WHERE dedupe_key IS NOT NULL
                    DO NOTHING
                    """,
                    (thread_id, role, content, dedupe_key),
                )

    @staticmethod
    def _summarize_input(input_text: str, max_len: int = 96) -> str:
        normalized = " ".join(input_text.split())
        if len(normalized) <= max_len:
            return normalized
        return f"{normalized[: max_len - 3]}..."

    def summarize_context(self, thread_id: str, max_messages: int = 8) -> str:
        messages = self.get_messages(thread_id)
        if not messages:
            return ""
        window = messages[-max_messages:]
        lines = [f"{item['role']}: {item['content']}" for item in window]
        return "\n".join(lines)


# Backward compatible alias for existing imports/tests.
SessionMemoryStore = PostgresSessionMemoryStore
