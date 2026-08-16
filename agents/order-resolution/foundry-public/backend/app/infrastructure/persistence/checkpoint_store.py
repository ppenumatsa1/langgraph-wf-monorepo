from __future__ import annotations

import json
from typing import Any

from app.core.database import postgres_db

_SELECT_COLUMNS = """
    checkpoint_id, thread_id, langgraph_checkpoint_id,
    langgraph_checkpoint_ns, interrupt_id, status, decision,
    audit_summary, reviewer, comments, created_at, updated_at, resolved_at
"""


class CheckpointStore:
    """Idempotent projection of the authoritative LangGraph interrupt."""

    def __init__(self) -> None:
        self._pool = postgres_db.get_pool()

    def get(self, checkpoint_id: str) -> dict[str, Any] | None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT {_SELECT_COLUMNS}
                    FROM workflow_interrupts
                    WHERE checkpoint_id = %s::uuid
                    """,
                    (checkpoint_id,),
                )
                row = cur.fetchone()
        return self._serialize(row) if row else None

    def get_unresolved_for_thread(self, thread_id: str) -> dict[str, Any] | None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"""
                    SELECT {_SELECT_COLUMNS}
                    FROM workflow_interrupts
                    WHERE thread_id = %s
                      AND status IN ('pending', 'resuming')
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (thread_id,),
                )
                row = cur.fetchone()
        return self._serialize(row) if row else None

    def list_reconciliation_thread_ids(self) -> list[str]:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT thread_id
                    FROM workflow_runs
                    WHERE status IN ('running', 'waiting_approval')
                    UNION
                    SELECT thread_id
                    FROM workflow_interrupts
                    WHERE status IN ('pending', 'resuming')
                    ORDER BY thread_id
                    """
                )
                return [str(row["thread_id"]) for row in cur.fetchall()]

    def reconcile_pending(
        self,
        *,
        checkpoint_id: str,
        thread_id: str,
        langgraph_checkpoint_id: str,
        langgraph_checkpoint_ns: str,
        interrupt_id: str,
        audit_summary: dict[str, Any],
    ) -> list[str]:
        stale_ids: list[str] = []
        with self._pool.connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT checkpoint_id
                        FROM workflow_interrupts
                        WHERE thread_id = %s
                          AND status IN ('pending', 'resuming')
                        FOR UPDATE
                        """,
                        (thread_id,),
                    )
                    stale_ids = [
                        str(row["checkpoint_id"])
                        for row in cur.fetchall()
                        if str(row["checkpoint_id"]) != checkpoint_id
                    ]
                    if stale_ids:
                        cur.execute(
                            """
                            UPDATE workflow_interrupts
                            SET status = 'orphaned',
                                audit_summary = audit_summary || %s::jsonb,
                                resolved_at = COALESCE(resolved_at, NOW()),
                                updated_at = NOW()
                            WHERE checkpoint_id = ANY(%s::uuid[])
                            """,
                            (
                                json.dumps(
                                    {
                                        "reconciliation": (
                                            "replaced_by_authoritative_graph_interrupt"
                                        )
                                    }
                                ),
                                stale_ids,
                            ),
                        )
                    cur.execute(
                        """
                        INSERT INTO workflow_interrupts (
                            checkpoint_id, thread_id, langgraph_checkpoint_id,
                            langgraph_checkpoint_ns, interrupt_id, status,
                            audit_summary, created_at, updated_at
                        )
                        VALUES (
                            %s::uuid, %s, %s, %s, %s, 'pending',
                            %s::jsonb, NOW(), NOW()
                        )
                        ON CONFLICT (checkpoint_id)
                        DO UPDATE SET
                            thread_id = EXCLUDED.thread_id,
                            langgraph_checkpoint_id = EXCLUDED.langgraph_checkpoint_id,
                            langgraph_checkpoint_ns = EXCLUDED.langgraph_checkpoint_ns,
                            interrupt_id = EXCLUDED.interrupt_id,
                            status = CASE
                                WHEN workflow_interrupts.status = 'resuming'
                                    THEN 'resuming'
                                ELSE 'pending'
                            END,
                            decision = CASE
                                WHEN workflow_interrupts.status = 'resuming'
                                    THEN workflow_interrupts.decision
                                ELSE NULL
                            END,
                            reviewer = CASE
                                WHEN workflow_interrupts.status = 'resuming'
                                    THEN workflow_interrupts.reviewer
                                ELSE NULL
                            END,
                            comments = CASE
                                WHEN workflow_interrupts.status = 'resuming'
                                    THEN workflow_interrupts.comments
                                ELSE NULL
                            END,
                            audit_summary = EXCLUDED.audit_summary,
                            resolved_at = NULL,
                            updated_at = NOW()
                        """,
                        (
                            checkpoint_id,
                            thread_id,
                            langgraph_checkpoint_id,
                            langgraph_checkpoint_ns,
                            interrupt_id,
                            json.dumps(audit_summary),
                        ),
                    )
        return stale_ids

    def begin_resolution(
        self,
        *,
        checkpoint_id: str,
        decision: str,
        reviewer: str,
        comments: str | None,
    ) -> dict[str, Any]:
        with self._pool.connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        f"""
                        SELECT {_SELECT_COLUMNS}
                        FROM workflow_interrupts
                        WHERE checkpoint_id = %s::uuid
                        FOR UPDATE
                        """,
                        (checkpoint_id,),
                    )
                    row = cur.fetchone()
                    if not row:
                        raise ValueError(f"Checkpoint not found: {checkpoint_id}")
                    existing_decision = row["decision"]
                    if existing_decision is not None and existing_decision != decision:
                        raise ValueError(
                            "Checkpoint was already resolved with a different decision."
                        )
                    if row["status"] in {"approved", "rejected"}:
                        result = self._serialize(row)
                        result["should_resume"] = False
                        return result
                    if row["status"] == "orphaned":
                        raise ValueError(f"Checkpoint is no longer resumable: {checkpoint_id}")
                    cur.execute(
                        f"""
                        UPDATE workflow_interrupts
                        SET status = 'resuming',
                            decision = %s,
                            reviewer = %s,
                            comments = %s,
                            updated_at = NOW()
                        WHERE checkpoint_id = %s::uuid
                        RETURNING {_SELECT_COLUMNS}
                        """,
                        (decision, reviewer, comments, checkpoint_id),
                    )
                    updated = cur.fetchone()
        if not updated:
            raise RuntimeError(f"Failed to claim checkpoint: {checkpoint_id}")
        result = self._serialize(updated)
        result["should_resume"] = True
        return result

    def complete_resolution(
        self,
        *,
        checkpoint_id: str,
        status: str,
    ) -> None:
        if status not in {"approved", "rejected"}:
            raise ValueError(f"Unsupported interrupt status: {status}")
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE workflow_interrupts
                    SET status = %s,
                        resolved_at = COALESCE(resolved_at, NOW()),
                        updated_at = NOW()
                    WHERE checkpoint_id = %s::uuid
                    """,
                    (status, checkpoint_id),
                )

    def mark_thread_orphaned(
        self,
        *,
        thread_id: str,
        reason: str,
    ) -> list[str]:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE workflow_interrupts
                    SET status = 'orphaned',
                        audit_summary = audit_summary || %s::jsonb,
                        resolved_at = COALESCE(resolved_at, NOW()),
                        updated_at = NOW()
                    WHERE thread_id = %s
                      AND status IN ('pending', 'resuming')
                    RETURNING checkpoint_id
                    """,
                    (
                        json.dumps({"reconciliation": reason}),
                        thread_id,
                    ),
                )
                return [str(row["checkpoint_id"]) for row in cur.fetchall()]

    @staticmethod
    def _serialize(row: Any) -> dict[str, Any]:
        return {
            "checkpoint_id": str(row["checkpoint_id"]),
            "thread_id": row["thread_id"],
            "langgraph_checkpoint_id": row["langgraph_checkpoint_id"],
            "langgraph_checkpoint_ns": row["langgraph_checkpoint_ns"],
            "interrupt_id": row["interrupt_id"],
            "status": row["status"],
            "decision": row["decision"],
            "audit_summary": row["audit_summary"] or {},
            "reviewer": row["reviewer"],
            "comments": row["comments"],
            "created_at": row["created_at"].isoformat(),
            "updated_at": row["updated_at"].isoformat(),
            "resolved_at": (
                row["resolved_at"].isoformat() if row["resolved_at"] is not None else None
            ),
        }


WorkflowInterruptRepository = CheckpointStore
