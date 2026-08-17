from __future__ import annotations

import json
import random
from datetime import UTC, datetime
from typing import Any

from app.core.database import postgres_db


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


class WorkflowRunRepository:
    def __init__(self) -> None:
        self._pool = postgres_db.get_pool()

    def create_workflow_run(
        self,
        workflow_run_id: str,
        application_id: str,
        applicant_name: str,
        workflow_type: str = "underwriting-langgraph",
    ) -> bool:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO workflow_runs (
                        id, workflow_type, application_id, applicant_name,
                        status, created_at, updated_at, started_at
                    ) VALUES (%s, %s, %s, %s, 'RUNNING', NOW(), NOW(), NOW())
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (workflow_run_id, workflow_type, application_id, applicant_name),
                )
                return cur.rowcount == 1

    def update_workflow_run_status(self, workflow_run_id: str, status: str) -> None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE workflow_runs
                    SET status = %s,
                        updated_at = NOW(),
                        completed_at = CASE
                            WHEN %s IN ('COMPLETED', 'FAILED')
                                THEN COALESCE(completed_at, NOW())
                            ELSE completed_at
                        END
                    WHERE id = %s
                    """,
                    (status, status, workflow_run_id),
                )
                if status in {"COMPLETED", "FAILED"}:
                    cur.execute(
                        """
                        UPDATE workflow_runs
                        SET duration_ms = GREATEST(
                            0,
                            CAST(EXTRACT(EPOCH FROM (completed_at - started_at)) * 1000 AS BIGINT)
                        )
                        WHERE id = %s
                          AND started_at IS NOT NULL
                          AND completed_at IS NOT NULL
                        """,
                        (workflow_run_id,),
                    )

    def get_workflow_run(self, workflow_run_id: str) -> dict[str, Any] | None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM workflow_runs WHERE id = %s",
                    (workflow_run_id,),
                )
                row = cur.fetchone()
        return dict(row) if row else None

    def get_safe_run_status(self, workflow_run_id: str) -> str | None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT status FROM workflow_runs WHERE id = %s",
                    (workflow_run_id,),
                )
                row = cur.fetchone()
        return str(row["status"]) if row else None

    def list_safe_event_summaries(
        self, workflow_run_id: str, *, limit: int
    ) -> list[dict[str, Any]]:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT event_type, executor_name, created_at
                    FROM workflow_events
                    WHERE workflow_run_id = %s
                    ORDER BY id DESC
                    LIMIT %s
                    """,
                    (workflow_run_id, limit),
                )
                rows = cur.fetchall()
        return [dict(row) for row in reversed(rows)]

    def get_safe_checkpoint_summary(self, workflow_run_id: str) -> tuple[int, Any | None]:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COUNT(*) AS checkpoint_count, MAX(created_at) AS latest_checkpoint_at
                    FROM workflow_checkpoints
                    WHERE workflow_run_id = %s
                    """,
                    (workflow_run_id,),
                )
                row = cur.fetchone()
        if not row:
            return 0, None
        return int(row["checkpoint_count"]), row["latest_checkpoint_at"]

    def get_safe_final_decision(self, workflow_run_id: str) -> str | None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT result_json
                    FROM underwriting_results
                    WHERE workflow_run_id = %s
                      AND check_type = 'final_decision'
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (workflow_run_id,),
                )
                row = cur.fetchone()
        if not row or not isinstance(row["result_json"], dict):
            return None
        decision = row["result_json"].get("decision")
        return str(decision) if isinstance(decision, str) else None

    def list_workflow_runs(
        self,
        *,
        search: str | None,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[int, list[dict[str, Any]]]:
        where: list[str] = []
        params: list[Any] = []
        if search:
            where.append(
                """
                (
                    LOWER(id) LIKE %s
                    OR LOWER(application_id) LIKE %s
                    OR LOWER(COALESCE(applicant_name, '')) LIKE %s
                )
                """
            )
            pattern = f"%{search.strip().lower()}%"
            params.extend([pattern, pattern, pattern])
        if status:
            where.append("status = %s")
            params.append(status.upper())
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""

        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    f"SELECT COUNT(*) AS total FROM workflow_runs {where_sql}",
                    tuple(params),
                )
                total = int(cur.fetchone()["total"])
                cur.execute(
                    f"""
                    SELECT *
                    FROM workflow_runs
                    {where_sql}
                    ORDER BY created_at DESC, id DESC
                    LIMIT %s OFFSET %s
                    """,
                    tuple([*params, limit, offset]),
                )
                rows = cur.fetchall()

        if not rows:
            return total, []

        run_ids = [str(row["id"]) for row in rows]
        decision_rows: dict[str, str] = {}
        checkpoint_rows: dict[str, dict[str, Any]] = {}
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT DISTINCT ON (workflow_run_id) workflow_run_id, result_json
                    FROM underwriting_results
                    WHERE workflow_run_id = ANY(%s)
                      AND check_type = 'final_decision'
                    ORDER BY workflow_run_id, id DESC
                    """,
                    (run_ids,),
                )
                for row in cur.fetchall():
                    result = row["result_json"] if isinstance(row["result_json"], dict) else {}
                    decision = result.get("decision")
                    if isinstance(decision, str):
                        decision_rows[str(row["workflow_run_id"])] = decision
                cur.execute(
                    """
                    SELECT workflow_run_id, COUNT(*) AS checkpoint_count, MAX(created_at) AS latest_checkpoint_at
                    FROM workflow_checkpoints
                    WHERE workflow_run_id = ANY(%s)
                    GROUP BY workflow_run_id
                    """,
                    (run_ids,),
                )
                for row in cur.fetchall():
                    checkpoint_rows[str(row["workflow_run_id"])] = {
                        "count": int(row["checkpoint_count"]),
                        "latest": row["latest_checkpoint_at"],
                    }

        items: list[dict[str, Any]] = []
        for row in rows:
            run_id = str(row["id"])
            checkpoint = checkpoint_rows.get(run_id, {"count": 0, "latest": None})
            items.append(
                {
                    "workflow_run_id": run_id,
                    "application_id": row["application_id"],
                    "applicant_name": row.get("applicant_name") or "Unknown applicant",
                    "status": row["status"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "final_decision": decision_rows.get(run_id),
                    "checkpoint_count": checkpoint["count"],
                    "latest_checkpoint_at": checkpoint["latest"],
                    "resumable": row["status"] == "CRASHED" and checkpoint["count"] > 0,
                }
            )
        return total, items

    def write_business_state(
        self,
        workflow_run_id: str,
        application_id: str,
        state_key: str,
        state_json: dict[str, Any],
    ) -> None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO business_state (
                        workflow_run_id, application_id, state_key, state_json, updated_at
                    ) VALUES (%s, %s, %s, %s::jsonb, NOW())
                    ON CONFLICT (workflow_run_id, state_key)
                    DO UPDATE SET
                        application_id = EXCLUDED.application_id,
                        state_json = EXCLUDED.state_json,
                        updated_at = NOW()
                    """,
                    (workflow_run_id, application_id, state_key, json.dumps(state_json)),
                )

    def list_business_state(self, workflow_run_id: str) -> list[dict[str, Any]]:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, workflow_run_id, application_id, state_key, state_json, updated_at
                    FROM business_state
                    WHERE workflow_run_id = %s
                    ORDER BY id ASC
                    """,
                    (workflow_run_id,),
                )
                rows = cur.fetchall()
        return [dict(row) for row in rows]

    def record_fan_in_progress(
        self,
        workflow_run_id: str,
        application_id: str,
        expected_checks: list[str],
        result_payload: dict[str, Any],
    ) -> None:
        check_key = str(result_payload["check_type"])
        with self._pool.connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT state_json
                        FROM business_state
                        WHERE workflow_run_id = %s AND state_key = 'aggregation_state'
                        FOR UPDATE
                        """,
                        (workflow_run_id,),
                    )
                    row = cur.fetchone()
                    state_json = (
                        row["state_json"] if row and isinstance(row["state_json"], dict) else {}
                    )
                    completed_checks = [
                        str(item)
                        for item in state_json.get("completed_checks", [])
                        if isinstance(item, str)
                    ]
                    child_results = state_json.get("child_results", {})
                    if not isinstance(child_results, dict):
                        child_results = {}
                    is_new = check_key not in completed_checks
                    child_results[check_key] = result_payload
                    if is_new:
                        completed_checks.append(check_key)
                    next_state = {
                        "expected_checks": expected_checks,
                        "completed_checks": completed_checks,
                        "child_results": child_results,
                    }
                    cur.execute(
                        """
                        INSERT INTO business_state (
                            workflow_run_id, application_id, state_key, state_json, updated_at
                        ) VALUES (%s, %s, 'aggregation_state', %s::jsonb, NOW())
                        ON CONFLICT (workflow_run_id, state_key)
                        DO UPDATE SET
                            application_id = EXCLUDED.application_id,
                            state_json = EXCLUDED.state_json,
                            updated_at = NOW()
                        """,
                        (workflow_run_id, application_id, json.dumps(next_state)),
                    )
                    if is_new:
                        cur.execute(
                            """
                            INSERT INTO workflow_events (
                                workflow_run_id, event_type, executor_name, payload_json, created_at
                            ) VALUES (%s, %s, %s, %s::jsonb, NOW())
                            """,
                            (
                                workflow_run_id,
                                "fan_in_result_received",
                                "fan_in_aggregator",
                                json.dumps(
                                    {
                                        "received_check": check_key,
                                        "completed_checks": completed_checks,
                                        "expected_checks": expected_checks,
                                    }
                                ),
                            ),
                        )

    def log_event(
        self,
        workflow_run_id: str,
        event_type: str,
        executor_name: str,
        payload_json: dict[str, Any],
    ) -> None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO workflow_events (
                        workflow_run_id, event_type, executor_name, payload_json, created_at
                    ) VALUES (%s, %s, %s, %s::jsonb, NOW())
                    """,
                    (workflow_run_id, event_type, executor_name, json.dumps(payload_json)),
                )
                cur.execute(
                    "UPDATE workflow_runs SET updated_at = NOW() WHERE id = %s",
                    (workflow_run_id,),
                )

    def list_events(self, workflow_run_id: str) -> list[dict[str, Any]]:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, workflow_run_id, event_type, executor_name, payload_json, created_at
                    FROM workflow_events
                    WHERE workflow_run_id = %s
                    ORDER BY id ASC
                    """,
                    (workflow_run_id,),
                )
                rows = cur.fetchall()
        return [dict(row) for row in rows]

    def get_idempotency(self, idempotency_key: str) -> dict[str, Any] | None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM idempotency_keys WHERE idempotency_key = %s",
                    (idempotency_key,),
                )
                row = cur.fetchone()
        return dict(row) if row else None

    def upsert_idempotency(
        self,
        idempotency_key: str,
        operation_name: str,
        status: str,
        result_json: dict[str, Any] | None,
    ) -> None:
        payload = json.dumps(result_json) if result_json is not None else None
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO idempotency_keys (
                        idempotency_key, operation_name, status, result_json, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s::jsonb, NOW(), NOW())
                    ON CONFLICT (idempotency_key)
                    DO UPDATE SET
                        operation_name = EXCLUDED.operation_name,
                        status = EXCLUDED.status,
                        result_json = EXCLUDED.result_json,
                        updated_at = NOW()
                    """,
                    (idempotency_key, operation_name, status, payload),
                )

    def save_underwriting_result(
        self,
        workflow_run_id: str,
        application_id: str,
        check_type: str,
        result_json: dict[str, Any],
        idempotency_key: str,
    ) -> None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO underwriting_results (
                        workflow_run_id, application_id, check_type,
                        result_json, idempotency_key, created_at, updated_at
                    ) VALUES (%s, %s, %s, %s::jsonb, %s, NOW(), NOW())
                    ON CONFLICT (idempotency_key) DO NOTHING
                    """,
                    (
                        workflow_run_id,
                        application_id,
                        check_type,
                        json.dumps(result_json),
                        idempotency_key,
                    ),
                )

    def count_underwriting_results_by_key(self, idempotency_key: str) -> int:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT COUNT(*) AS count FROM underwriting_results WHERE idempotency_key = %s",
                    (idempotency_key,),
                )
                row = cur.fetchone()
        return int(row["count"] if row else 0)

    def get_underwriting_result_by_key(self, idempotency_key: str) -> dict[str, Any] | None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT result_json
                    FROM underwriting_results
                    WHERE idempotency_key = %s
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (idempotency_key,),
                )
                row = cur.fetchone()
        if not row or not isinstance(row["result_json"], dict):
            return None
        return row["result_json"]

    def list_underwriting_results(self, workflow_run_id: str) -> list[dict[str, Any]]:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM underwriting_results
                    WHERE workflow_run_id = %s
                    ORDER BY id ASC
                    """,
                    (workflow_run_id,),
                )
                rows = cur.fetchall()
        return [dict(row) for row in rows]

    def update_latest_output(self, workflow_run_id: str, output: dict[str, Any]) -> None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE workflow_runs
                    SET latest_output = %s::jsonb,
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (json.dumps(output), workflow_run_id),
                )

    def record_checkpoint(
        self,
        workflow_run_id: str,
        checkpoint_id: str,
        checkpoint_ns: str,
        parent_checkpoint_id: str | None,
        metadata_json: dict[str, Any],
    ) -> None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO workflow_checkpoints (
                        workflow_run_id, checkpoint_ns, checkpoint_id,
                        parent_checkpoint_id, metadata_json, created_at
                    ) VALUES (%s, %s, %s, %s, %s::jsonb, NOW())
                    ON CONFLICT (workflow_run_id, checkpoint_ns, checkpoint_id)
                    DO NOTHING
                    """,
                    (
                        workflow_run_id,
                        checkpoint_ns,
                        checkpoint_id,
                        parent_checkpoint_id,
                        json.dumps(metadata_json),
                    ),
                )

    def list_checkpoints(self, workflow_run_id: str) -> list[dict[str, Any]]:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT workflow_run_id, checkpoint_ns, checkpoint_id,
                           parent_checkpoint_id, metadata_json, created_at
                    FROM workflow_checkpoints
                    WHERE workflow_run_id = %s
                    ORDER BY created_at ASC, checkpoint_id ASC
                    """,
                    (workflow_run_id,),
                )
                rows = cur.fetchall()
        return [dict(row) for row in rows]

    def latest_checkpoint_id(self, workflow_run_id: str) -> str | None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT checkpoint_id
                    FROM workflow_checkpoints
                    WHERE workflow_run_id = %s
                    ORDER BY created_at DESC, checkpoint_id DESC
                    LIMIT 1
                    """,
                    (workflow_run_id,),
                )
                row = cur.fetchone()
        return str(row["checkpoint_id"]) if row else None

    def should_fail_credit_randomly(self, threshold: float = 0.5) -> bool:
        return random.random() < threshold

    def reset_all(self) -> None:
        with self._pool.connection() as conn:
            with conn.transaction():
                with conn.cursor() as cur:
                    for table in (
                        "workflow_events",
                        "underwriting_results",
                        "business_state",
                        "workflow_checkpoints",
                        "idempotency_keys",
                        "checkpoint_writes",
                        "checkpoint_blobs",
                        "checkpoints",
                        "checkpoint_migrations",
                        "workflow_runs",
                    ):
                        cur.execute(f"TRUNCATE TABLE {table} CASCADE")
