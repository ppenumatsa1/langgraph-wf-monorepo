from __future__ import annotations

import atexit
import os
from pathlib import Path
from threading import RLock

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


class PostgresDatabase:
    def __init__(self) -> None:
        self._pool: ConnectionPool | None = None
        self._lock = RLock()

    @property
    def database_url(self) -> str:
        value = os.getenv("DATABASE_URL", "").strip()
        if value:
            return value.replace("postgresql+psycopg://", "postgresql://", 1)

        host = os.getenv("DB_HOST", "localhost").strip() or "localhost"
        port = int(os.getenv("DB_PORT", "5433"))
        name = os.getenv("DB_NAME", "underwriting").strip() or "underwriting"
        user = os.getenv("DB_USER", "underwriting").strip() or "underwriting"
        password = os.getenv("DB_PASSWORD", "underwriting")
        sslmode = os.getenv("DB_SSLMODE", "prefer").strip() or "prefer"
        return f"postgresql://{user}:{password}@{host}:{port}/{name}?sslmode={sslmode}"

    def get_pool(self) -> ConnectionPool:
        with self._lock:
            if self._pool is None:
                self._pool = ConnectionPool(
                    conninfo=self.database_url,
                    min_size=1,
                    max_size=max(2, int(os.getenv("WORKFLOW_POOL_MAX_SIZE", "10"))),
                    open=True,
                    kwargs={
                        "autocommit": True,
                        "prepare_threshold": 0,
                        "row_factory": dict_row,
                    },
                )
            return self._pool

    def close(self) -> None:
        with self._lock:
            if self._pool is not None:
                self._pool.close()
                self._pool = None

    def bootstrap_application_schema(self) -> None:
        schema_path = Path(__file__).resolve().parents[1] / "sql" / "schema.sql"
        schema_sql = schema_path.read_text(encoding="utf-8")
        with self.get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(schema_sql, prepare=False)

    def verify_runtime_schema(self) -> None:
        required_tables = (
            "workflow_runs",
            "business_state",
            "workflow_events",
            "workflow_checkpoints",
            "underwriting_results",
            "idempotency_keys",
            "checkpoint_migrations",
            "checkpoints",
            "checkpoint_blobs",
            "checkpoint_writes",
        )
        with self.get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT relname
                    FROM pg_class
                    WHERE relkind = 'r'
                      AND relname = ANY(%s)
                    """,
                    (list(required_tables),),
                )
                present = {str(row["relname"]) for row in cur.fetchall()}
        missing = sorted(set(required_tables) - present)
        if missing:
            raise RuntimeError(
                "Database schema is not bootstrapped; missing tables: "
                + ", ".join(missing)
                + ". Run `python -m app.sql.bootstrap` with an administrator credential."
            )


postgres_db = PostgresDatabase()
atexit.register(postgres_db.close)
