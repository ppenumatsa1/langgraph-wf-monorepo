from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.api.v1.schemas import (
    PendingApproval,
    SessionMessage,
    WorkflowEvent,
    WorkflowRunDetailsResponse,
    WorkflowRunListItem,
    WorkflowRunMetadata,
    WorkflowRunStatus,
)
from app.core.database import postgres_db
from psycopg.rows import dict_row


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    return str(value)


def _duration_ms(started_at: str | None, completed_at: str | None) -> int | None:
    if not started_at or not completed_at:
        return None
    try:
        started = datetime.fromisoformat(started_at)
        completed = datetime.fromisoformat(completed_at)
    except ValueError:
        return None
    return max(0, int((completed - started).total_seconds() * 1000))


class WorkflowRunRepository:
    def __init__(self) -> None:
        self._pool = postgres_db.get_pool()

    def create_workflow_run(
        self,
        thread_id: str,
        input_text: str,
        session_id: str | None = None,
        customer_id: str | None = None,
    ) -> dict[str, Any]:
        now = _utc_now_iso()
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                if session_id:
                    cur.execute(
                        """
                        INSERT INTO sessions (session_id, customer_id, created_at, updated_at)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT (session_id)
                        DO UPDATE SET
                            customer_id = COALESCE(EXCLUDED.customer_id, sessions.customer_id),
                            updated_at = EXCLUDED.updated_at
                        """,
                        (session_id, customer_id, now, now),
                    )
                cur.execute(
                    """
                    INSERT INTO workflow_runs (
                        thread_id, session_id, status, input, input_summary,
                        created_at, updated_at, started_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (thread_id) DO NOTHING
                    """,
                    (
                        thread_id,
                        session_id,
                        "running",
                        input_text,
                        self._summarize_input(input_text),
                        now,
                        now,
                        now,
                    ),
                )
                cur.execute(
                    """
                    SELECT thread_id, session_id, status, input, input_summary,
                           created_at, updated_at
                    FROM workflow_runs
                    WHERE thread_id = %s
                    """,
                    (thread_id,),
                )
                row = cur.fetchone()
                if not row:
                    raise RuntimeError(f"Failed to create workflow run: {thread_id}")
                return {
                    "thread_id": row["thread_id"],
                    "session_id": row["session_id"],
                    "status": row["status"],
                    "input": row["input"],
                    "input_summary": row["input_summary"],
                    "created_at": _as_iso(row["created_at"]),
                    "updated_at": _as_iso(row["updated_at"]),
                }

    def create_or_get_responses_dispatch(
        self,
        *,
        idempotency_key: str,
        request_hash: str,
        run_id: str,
        thread_id: str,
    ) -> dict[str, Any]:
        now = _utc_now_iso()
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO responses_dispatches (
                        idempotency_key, request_hash, run_id, thread_id, status, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (idempotency_key) DO NOTHING
                    RETURNING idempotency_key
                    """,
                    (idempotency_key, request_hash, run_id, thread_id, "pending", now, now),
                )
                created = cur.fetchone() is not None
                cur.execute(
                    """
                    SELECT idempotency_key, request_hash, run_id, thread_id, status
                    FROM responses_dispatches
                    WHERE idempotency_key = %s
                    """,
                    (idempotency_key,),
                )
                row = cur.fetchone()
                if not row:
                    raise RuntimeError(f"Failed to create Responses dispatch: {idempotency_key}")
                if row["request_hash"] != request_hash:
                    raise ValueError("Idempotency key was already used with a different request.")
                result = dict(row)
                result["created"] = created
                return result

    def update_responses_dispatch_status(self, idempotency_key: str, status: str) -> None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE responses_dispatches
                    SET status = %s, updated_at = %s
                    WHERE idempotency_key = %s
                    """,
                    (status, _utc_now_iso(), idempotency_key),
                )

    def update_responses_dispatch_thread(self, idempotency_key: str, thread_id: str) -> None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE responses_dispatches
                    SET thread_id = %s, updated_at = %s
                    WHERE idempotency_key = %s
                    """,
                    (thread_id, _utc_now_iso(), idempotency_key),
                )

    def list_workflow_runs(
        self,
        page: int,
        page_size: int,
        status: WorkflowRunStatus | None = None,
    ) -> tuple[list[WorkflowRunListItem], int]:
        offset = (page - 1) * page_size
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                if status:
                    cur.execute(
                        "SELECT COUNT(*) AS total FROM workflow_runs WHERE status = %s",
                        (status,),
                    )
                    total_row = cur.fetchone()
                    total = int(total_row["total"]) if total_row else 0
                    cur.execute(
                        """
                        SELECT thread_id, status, input_summary, created_at, updated_at
                        FROM workflow_runs
                        WHERE status = %s
                        ORDER BY created_at DESC
                        LIMIT %s OFFSET %s
                        """,
                        (status, page_size, offset),
                    )
                else:
                    cur.execute("SELECT COUNT(*) AS total FROM workflow_runs")
                    total_row = cur.fetchone()
                    total = int(total_row["total"]) if total_row else 0
                    cur.execute(
                        """
                        SELECT thread_id, status, input_summary, created_at, updated_at
                        FROM workflow_runs
                        ORDER BY created_at DESC
                        LIMIT %s OFFSET %s
                        """,
                        (page_size, offset),
                    )

                rows = cur.fetchall()

        items = [
            WorkflowRunListItem(
                thread_id=row["thread_id"],
                status=row["status"],
                input_summary=row["input_summary"],
                created_at=_as_iso(row["created_at"]) or _utc_now_iso(),
                updated_at=_as_iso(row["updated_at"]) or _utc_now_iso(),
            )
            for row in rows
        ]
        return items, total

    def list_workflow_events(
        self,
        thread_id: str,
        limit: int,
        cursor: str | None = None,
    ) -> tuple[list[WorkflowEvent], str | None, bool]:
        query = """
            SELECT id, type, thread_id, timestamp, payload
            FROM workflow_events
            WHERE thread_id = %s
        """
        params: list[Any] = [thread_id]
        if cursor:
            try:
                cursor_timestamp, cursor_id = cursor.split("|", 1)
            except ValueError:
                cursor_timestamp, cursor_id = "", ""
            if cursor_timestamp and cursor_id:
                query += """
                    AND (
                        timestamp > %s::timestamptz
                        OR (timestamp = %s::timestamptz AND id > %s::uuid)
                    )
                """
                params.extend([cursor_timestamp, cursor_timestamp, cursor_id])
        query += """
            ORDER BY timestamp ASC, id ASC
            LIMIT %s
        """
        params.append(limit + 1)

        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, tuple(params))
                rows = cur.fetchall()

        has_more = len(rows) > limit
        page_rows = rows[:limit]
        events = [
            WorkflowEvent(
                id=str(row["id"]),
                type=row["type"],
                thread_id=row["thread_id"],
                timestamp=_as_iso(row["timestamp"]) or _utc_now_iso(),
                payload=row["payload"] or {},
            )
            for row in page_rows
        ]
        next_cursor = f"{events[-1].timestamp}|{events[-1].id}" if has_more and events else None
        return events, next_cursor, has_more

    def list_session_messages(
        self,
        session_id: str,
        limit: int,
        cursor: int | None = None,
    ) -> tuple[list[SessionMessage], str | None, bool]:
        query = """
            SELECT cm.id, wr.session_id, cm.thread_id, cm.role, cm.content, cm.created_at
            FROM conversation_messages cm
            INNER JOIN workflow_runs wr
                ON wr.thread_id = cm.thread_id
            WHERE wr.session_id = %s
        """
        params: list[Any] = [session_id]
        if cursor is not None:
            query += " AND cm.id > %s"
            params.append(cursor)
        query += """
            ORDER BY cm.id ASC
            LIMIT %s
        """
        params.append(limit + 1)

        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, tuple(params))
                rows = cur.fetchall()

        has_more = len(rows) > limit
        page_rows = rows[:limit]
        messages = [
            SessionMessage(
                id=int(row["id"]),
                session_id=row["session_id"],
                thread_id=row["thread_id"],
                role=row["role"],
                content=row["content"],
                created_at=_as_iso(row["created_at"]) or _utc_now_iso(),
            )
            for row in page_rows
        ]
        next_cursor = str(messages[-1].id) if has_more and messages else None
        return messages, next_cursor, has_more

    def get_workflow_run(self, thread_id: str) -> WorkflowRunDetailsResponse | None:
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT thread_id, status, input, latest_output,
                           started_at, completed_at, duration_ms, current_stage
                    FROM workflow_runs
                    WHERE thread_id = %s
                    """,
                    (thread_id,),
                )
                run = cur.fetchone()
                if not run:
                    return None

                cur.execute(
                    """
                    SELECT id, type, thread_id, timestamp, payload
                    FROM workflow_events
                    WHERE thread_id = %s
                    ORDER BY timestamp ASC, id ASC
                    """,
                    (thread_id,),
                )
                event_rows = cur.fetchall()

                cur.execute(
                    """
                    SELECT approval_id, checkpoint_id, reviewer, comments,
                           status, requested_at, resolved_at
                    FROM approvals
                    WHERE thread_id = %s
                    ORDER BY requested_at DESC
                    """,
                    (thread_id,),
                )
                approval_rows = cur.fetchall()

        events = [
            WorkflowEvent(
                id=str(row["id"]),
                type=row["type"],
                thread_id=row["thread_id"],
                timestamp=_as_iso(row["timestamp"]) or _utc_now_iso(),
                payload=row["payload"] or {},
            )
            for row in event_rows
        ]
        approvals = [
            PendingApproval(
                approval_id=str(row["approval_id"]),
                checkpoint_id=str(row["checkpoint_id"]),
                action=None,
                order_id=None,
                amount=None,
                question=None,
                reviewer=row["reviewer"],
                comments=row["comments"],
                status=row["status"],
                requested_at=_as_iso(row["requested_at"]) or _utc_now_iso(),
                resolved_at=_as_iso(row["resolved_at"]),
            )
            for row in approval_rows
        ]

        metadata = WorkflowRunMetadata(
            thread_id=run["thread_id"],
            status=run["status"],
            started_at=_as_iso(run["started_at"]),
            completed_at=_as_iso(run["completed_at"]),
            duration_ms=run["duration_ms"],
            current_stage=run["current_stage"],
        )

        return WorkflowRunDetailsResponse(
            thread_id=run["thread_id"],
            status=run["status"],
            input=run["input"],
            events=events,
            pending_approvals=approvals,
            latest_output=run["latest_output"],
            metadata=metadata,
        )

    def append_workflow_event(self, thread_id: str, event: WorkflowEvent) -> None:
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO workflow_events (id, thread_id, type, timestamp, payload)
                    VALUES (%s::uuid, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (
                        event.id,
                        thread_id,
                        event.type,
                        event.timestamp,
                        self._json_dumps(event.payload),
                    ),
                )
                cur.execute(
                    "UPDATE workflow_runs SET updated_at = %s WHERE thread_id = %s",
                    (_utc_now_iso(), thread_id),
                )

    def workflow_event_exists(self, event_id: str) -> bool:
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT 1 FROM workflow_events WHERE id = %s::uuid",
                    (event_id,),
                )
                return cur.fetchone() is not None

    def update_workflow_status(self, thread_id: str, status: WorkflowRunStatus) -> None:
        now = _utc_now_iso()
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    UPDATE workflow_runs
                    SET status = %s,
                        updated_at = %s
                    WHERE thread_id = %s
                    """,
                    (status, now, thread_id),
                )
                if status in {"completed", "failed", "escalated"}:
                    cur.execute(
                        """
                        UPDATE workflow_runs
                        SET completed_at = COALESCE(completed_at, %s)
                        WHERE thread_id = %s
                        """,
                        (now, thread_id),
                    )
                    cur.execute(
                        """
                        SELECT started_at, completed_at
                        FROM workflow_runs
                        WHERE thread_id = %s
                        """,
                        (thread_id,),
                    )
                    row = cur.fetchone()
                    if row:
                        duration = _duration_ms(
                            _as_iso(row["started_at"]),
                            _as_iso(row["completed_at"]),
                        )
                        cur.execute(
                            """
                            UPDATE workflow_runs
                            SET duration_ms = %s
                            WHERE thread_id = %s
                            """,
                            (duration, thread_id),
                        )

    def update_current_stage(self, thread_id: str, stage: str | None) -> None:
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    UPDATE workflow_runs
                    SET current_stage = %s,
                        updated_at = %s
                    WHERE thread_id = %s
                    """,
                    (stage, _utc_now_iso(), thread_id),
                )

    def update_latest_output(self, thread_id: str, output: dict[str, Any]) -> None:
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    UPDATE workflow_runs
                    SET latest_output = %s::jsonb,
                        updated_at = %s
                    WHERE thread_id = %s
                    """,
                    (self._json_dumps(output), _utc_now_iso(), thread_id),
                )

    def get_pending_approval_context(self, checkpoint_id: str) -> dict[str, Any] | None:
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT thread_id, status
                    FROM approvals
                    WHERE checkpoint_id = %s::uuid
                    ORDER BY requested_at DESC
                    LIMIT 1
                    """,
                    (checkpoint_id,),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return {
                    "thread_id": row["thread_id"],
                    "status": row["status"],
                }

    def add_pending_approval(self, thread_id: str, approval: dict[str, Any]) -> None:
        now = _utc_now_iso()
        approval_item = {
            "approval_id": str(uuid4()),
            "checkpoint_id": str(approval.get("checkpoint_id", "")),
            "reviewer": None,
            "comments": None,
            "status": "pending",
            "requested_at": now,
            "resolved_at": None,
        }
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO approvals (
                        approval_id, thread_id, checkpoint_id,
                        reviewer, comments, status,
                        requested_at, resolved_at
                    )
                    VALUES (
                        %s::uuid, %s, %s::uuid,
                        %s, %s, %s,
                        %s, %s
                    )
                    ON CONFLICT (checkpoint_id)
                    DO UPDATE SET
                        thread_id = EXCLUDED.thread_id,
                        status = 'pending',
                        reviewer = NULL,
                        comments = NULL,
                        resolved_at = NULL
                    """,
                    (
                        approval_item["approval_id"],
                        thread_id,
                        approval_item["checkpoint_id"],
                        approval_item["reviewer"],
                        approval_item["comments"],
                        approval_item["status"],
                        approval_item["requested_at"],
                        approval_item["resolved_at"],
                    ),
                )
                cur.execute(
                    "UPDATE workflow_runs SET updated_at = %s WHERE thread_id = %s",
                    (now, thread_id),
                )

    def remove_approval_projection(self, checkpoint_id: str) -> None:
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "DELETE FROM approvals WHERE checkpoint_id = %s::uuid",
                    (checkpoint_id,),
                )

    def resolve_approval(
        self,
        thread_id: str,
        checkpoint_id: str,
        decision: str,
        comment: str | None,
        reviewer: str | None,
    ) -> None:
        now = _utc_now_iso()
        with self._pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    UPDATE approvals
                    SET status = %s,
                        reviewer = %s,
                        comments = %s,
                        resolved_at = %s
                    WHERE thread_id = %s
                      AND checkpoint_id = %s::uuid
                      AND status = 'pending'
                    """,
                    (
                        "approved" if decision == "approve" else "rejected",
                        reviewer,
                        comment,
                        now,
                        thread_id,
                        checkpoint_id,
                    ),
                )
                cur.execute(
                    "UPDATE workflow_runs SET updated_at = %s WHERE thread_id = %s",
                    (now, thread_id),
                )

    @staticmethod
    def _summarize_input(input_text: str, max_len: int = 96) -> str:
        normalized = " ".join(input_text.split())
        if len(normalized) <= max_len:
            return normalized
        return f"{normalized[: max_len - 3]}..."

    @staticmethod
    def _as_optional_str(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _json_dumps(value: dict[str, Any]) -> str:
        import json

        return json.dumps(value)
