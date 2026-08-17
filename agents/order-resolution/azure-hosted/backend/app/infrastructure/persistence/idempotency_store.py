from __future__ import annotations

import json
from collections.abc import Callable

from app.core.database import postgres_db


class IdempotencyInProgressError(RuntimeError):
    """Raised when an idempotent operation is already in progress."""


class IdempotencyStore:
    def __init__(self) -> None:
        self._pool = postgres_db.get_pool()

    @staticmethod
    def compose_key(workflow_run_id: str, step_name: str, business_id: str) -> str:
        return f"{workflow_run_id}:{step_name}:{business_id}"

    def execute_once(
        self,
        *,
        workflow_run_id: str,
        step_name: str,
        business_id: str,
        operation: Callable[[], str],
    ) -> tuple[str, bool]:
        key = self.compose_key(workflow_run_id, step_name, business_id)
        existing = self._get_result(key)
        if existing is not None:
            return existing, True

        claimed = self._claim_key(
            key=key,
            workflow_run_id=workflow_run_id,
            step_name=step_name,
            business_id=business_id,
        )
        if not claimed:
            replayed = self._get_result(key)
            if replayed is None:
                raise IdempotencyInProgressError(f"Idempotency key in progress: {key}")
            return replayed, True

        try:
            result = operation()
        except Exception:
            self._mark_failed(key)
            raise

        self._mark_completed(key, result)
        return result, False

    def _claim_key(
        self, *, key: str, workflow_run_id: str, step_name: str, business_id: str
    ) -> bool:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO idempotency_keys (
                        idempotency_key, workflow_run_id, step_name, business_id, status
                    ) VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (idempotency_key)
                    DO UPDATE SET
                        status = EXCLUDED.status,
                        updated_at = NOW()
                    WHERE idempotency_keys.status = 'failed'
                    """,
                    (key, workflow_run_id, step_name, business_id, "in_progress"),
                )
                return cur.rowcount == 1

    def _mark_completed(self, key: str, result: str) -> None:
        payload = json.dumps({"value": result})
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE idempotency_keys
                    SET status = %s,
                        result = %s::jsonb,
                        updated_at = NOW()
                    WHERE idempotency_key = %s
                    """,
                    ("completed", payload, key),
                )

    def _mark_failed(self, key: str) -> None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE idempotency_keys
                    SET status = %s,
                        updated_at = NOW()
                    WHERE idempotency_key = %s
                    """,
                    ("failed", key),
                )

    def _get_result(self, key: str) -> str | None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT status, result
                    FROM idempotency_keys
                    WHERE idempotency_key = %s
                    """,
                    (key,),
                )
                row = cur.fetchone()
                if not row or row["status"] != "completed":
                    return None
                result = row["result"] or {}
                return str(result.get("value", ""))
