from __future__ import annotations

import atexit
import os
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from urllib.parse import parse_qs, urlsplit

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/langgraph_workflow"


_SECURE_SSL_MODES = {"require", "verify-ca", "verify-full"}


@dataclass(frozen=True)
class PostgresPoolConfig:
    min_size: int
    max_size: int
    max_idle_seconds: float
    application_name: str


def _env_int(name: str, default: int, *, minimum: int) -> int:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


def _env_float(name: str, default: float, *, minimum: float) -> float:
    raw_value = os.getenv(name, str(default)).strip()
    try:
        value = float(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if value < minimum:
        raise ValueError(f"{name} must be at least {minimum}")
    return value


def postgres_pool_config() -> PostgresPoolConfig:
    min_size = _env_int("POSTGRES_POOL_MIN_SIZE", 1, minimum=0)
    max_size = _env_int("POSTGRES_POOL_MAX_SIZE", 10, minimum=1)
    if max_size < min_size:
        raise ValueError("POSTGRES_POOL_MAX_SIZE must be at least POSTGRES_POOL_MIN_SIZE")
    application_name = os.getenv("POSTGRES_APPLICATION_NAME", "langgraph-order-resolution").strip()
    if not application_name:
        raise ValueError("POSTGRES_APPLICATION_NAME must not be empty")
    return PostgresPoolConfig(
        min_size=min_size,
        max_size=max_size,
        max_idle_seconds=_env_float("POSTGRES_POOL_MAX_IDLE_SECONDS", 600.0, minimum=1.0),
        application_name=application_name,
    )


def is_connection_placeholder(value: str) -> bool:
    stripped = value.strip()
    return stripped.startswith("${") and stripped.endswith("}")


def _env_enabled(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def _is_foundry_runtime() -> bool:
    return os.getenv("APP_ENV", "").strip().lower().startswith("foundry-private")


def _validate_foundry_runtime_database_url(value: str) -> None:
    if is_connection_placeholder(value):
        raise RuntimeError(
            "DATABASE_URL contains an unresolved Foundry project connection placeholder."
        )
    parsed = urlsplit(value.replace("postgresql+psycopg://", "postgresql://", 1))
    sslmode = parse_qs(parsed.query).get("sslmode", [""])[0].strip().lower()
    if sslmode not in _SECURE_SSL_MODES:
        raise RuntimeError("DATABASE_URL must require TLS for the Foundry-private hosted runtime.")
    if not _env_enabled("DB_SCHEMA_MANAGED_EXTERNALLY"):
        raise RuntimeError(
            "DB_SCHEMA_MANAGED_EXTERNALLY=true is required for the Foundry-private hosted runtime."
        )


class PostgresDatabase:
    def __init__(self) -> None:
        self._pool: ConnectionPool | None = None
        self._lock = RLock()

    @property
    def database_url(self) -> str:
        value = os.getenv("DATABASE_URL", "").strip()
        if value:
            if _is_foundry_runtime():
                _validate_foundry_runtime_database_url(value)
            return value.replace("postgresql+psycopg://", "postgresql://", 1)
        if _is_foundry_runtime():
            raise RuntimeError("DATABASE_URL must be set for the Foundry-private hosted runtime.")
        return DEFAULT_DATABASE_URL

    def get_pool(self) -> ConnectionPool:
        with self._lock:
            if self._pool is None:
                config = postgres_pool_config()
                self._pool = ConnectionPool(
                    conninfo=self.database_url,
                    min_size=config.min_size,
                    max_size=config.max_size,
                    max_idle=config.max_idle_seconds,
                    open=True,
                    kwargs={
                        "application_name": config.application_name,
                        "autocommit": True,
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
                cur.execute(schema_sql)

    def verify_runtime_schema(self) -> None:
        required_tables = (
            "workflow_runs",
            "workflow_events",
            "conversation_messages",
            "workflow_interrupts",
            "approvals",
            "idempotency_keys",
            "responses_dispatches",
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
        with self.get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT table_name, column_name
                    FROM information_schema.columns
                    WHERE table_schema = 'public'
                      AND table_name IN ('workflow_interrupts', 'approvals')
                    """
                )
                columns = {
                    (str(row["table_name"]), str(row["column_name"])) for row in cur.fetchall()
                }
        if ("workflow_interrupts", "audit_summary") not in columns:
            raise RuntimeError("Database schema is missing workflow_interrupts.audit_summary.")
        forbidden_projection_columns = {
            ("workflow_interrupts", "state"),
            ("approvals", "action"),
            ("approvals", "order_id"),
            ("approvals", "amount"),
            ("approvals", "question"),
        }
        present_forbidden = sorted(forbidden_projection_columns & columns)
        if present_forbidden:
            raise RuntimeError(
                "Approval projections contain authoritative business-state columns: "
                + ", ".join(f"{table}.{column}" for table, column in present_forbidden)
            )


postgres_db = PostgresDatabase()
atexit.register(postgres_db.close)
