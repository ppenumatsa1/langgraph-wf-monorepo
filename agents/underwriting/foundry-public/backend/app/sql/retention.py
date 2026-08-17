from __future__ import annotations

from app.core.database import postgres_db

_CHECKPOINT_TABLES = (
    "checkpoint_writes",
    "checkpoint_blobs",
    "checkpoints",
)


def prune_completed_checkpoints(retention_days: int) -> dict[str, int]:
    if retention_days < 1:
        raise ValueError("retention_days must be a positive integer.")

    deleted: dict[str, int] = {}
    with postgres_db.get_pool().connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                for table_name in _CHECKPOINT_TABLES:
                    cur.execute(
                        f"""
                        DELETE FROM {table_name} graph_state
                        USING workflow_runs runs
                        WHERE graph_state.thread_id = runs.id
                          AND runs.status IN ('COMPLETED', 'FAILED')
                          AND runs.completed_at
                              < NOW() - make_interval(days => %s)
                        """,
                        (retention_days,),
                    )
                    deleted[table_name] = cur.rowcount
    return deleted


__all__ = ["prune_completed_checkpoints"]
