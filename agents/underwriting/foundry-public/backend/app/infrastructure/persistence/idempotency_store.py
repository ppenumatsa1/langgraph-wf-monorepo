from __future__ import annotations

import json
from collections.abc import Callable

from app.core.database import postgres_db


class IdempotencyInProgressError(RuntimeError):
    pass


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
        operation: Callable[[], dict[str, object]],
    ) -> tuple[dict[str, object], bool]:
        key = self.compose_key(workflow_run_id, step_name, business_id)
        existing = self._get_result(key)
        if existing is not None:
            return existing, True

        claimed = self._claim_key(
            key=key,
            operation_name=step_name,
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

    def _claim_key(self, *, key: str, operation_name: str) -> bool:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO idempotency_keys (
                        idempotency_key, operation_name, status, result_json, created_at, updated_at
                    ) VALUES (%s, %s, 'in_progress', NULL, NOW(), NOW())
                    ON CONFLICT (idempotency_key)
                    DO UPDATE SET
                        status = EXCLUDED.status,
                        updated_at = NOW()
                    WHERE idempotency_keys.status = 'failed'
                    """,
                    (key, operation_name),
                )
                return cur.rowcount == 1

    def _mark_completed(self, key: str, result: dict[str, object]) -> None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE idempotency_keys
                    SET status = 'completed',
                        result_json = %s::jsonb,
                        updated_at = NOW()
                    WHERE idempotency_key = %s
                    """,
                    (json.dumps(result), key),
                )

    def _mark_failed(self, key: str) -> None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE idempotency_keys
                    SET status = 'failed',
                        updated_at = NOW()
                    WHERE idempotency_key = %s
                    """,
                    (key,),
                )

    def _get_result(self, key: str) -> dict[str, object] | None:
        with self._pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT status, result_json FROM idempotency_keys WHERE idempotency_key = %s",
                    (key,),
                )
                row = cur.fetchone()
        if not row or row["status"] != "completed" or not isinstance(row["result_json"], dict):
            return None
        return row["result_json"]
