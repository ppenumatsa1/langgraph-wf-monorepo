from __future__ import annotations

from pathlib import Path

from app.core.database import PostgresDatabase


def test_database_url_normalizes_psycopg_dialect(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://user:password@server.postgres.database.azure.com:5432/"
        "order_resolution?sslmode=require",
    )

    assert "postgresql+psycopg" not in PostgresDatabase().database_url


def test_runtime_schema_verification_is_read_only(monkeypatch) -> None:
    database = PostgresDatabase()
    statements: list[str] = []

    class _Cursor:
        def execute(self, statement, parameters=None):
            statements.append(str(statement))

        def fetchall(self):
            if len(statements) > 1:
                return [
                    {
                        "table_name": "workflow_interrupts",
                        "column_name": "audit_summary",
                    },
                    {
                        "table_name": "workflow_interrupts",
                        "column_name": "checkpoint_id",
                    },
                    {"table_name": "approvals", "column_name": "approval_id"},
                ]
            names = (
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
            return [{"relname": name} for name in names]

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

    class _Connection:
        def cursor(self):
            return _Cursor()

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

    class _Pool:
        def connection(self):
            return _Connection()

    monkeypatch.setattr(database, "get_pool", lambda: _Pool())

    database.verify_runtime_schema()

    sql = " ".join(statements).lower()
    assert "select" in sql
    assert all(token not in sql for token in ("create ", "alter ", "drop "))


def test_schema_bootstrap_is_explicit_admin_operation() -> None:
    database_source = Path("app/core/database.py").read_text(encoding="utf-8")
    container_source = Path("app/core/container.py").read_text(encoding="utf-8")

    assert "bootstrap_application_schema" in database_source
    assert "bootstrap_application_schema" not in container_source


def test_runtime_grants_do_not_grant_schema_creation_or_ownership() -> None:
    grants = Path("app/sql/runtime_grants.sql").read_text(encoding="utf-8").lower()

    assert "grant usage on schema" in grants
    assert "grant select, insert, update, delete" in grants
    assert "grant create" not in grants
    assert "alter owner" not in grants


def test_checkpoint_retention_never_prunes_unresolved_threads() -> None:
    retention = Path("app/sql/checkpoint_retention.sql").read_text(encoding="utf-8").lower()

    assert "checkpoint_writes" in retention
    assert "checkpoint_blobs" in retention
    assert "checkpoints" in retention
    assert "interrupts.status in ('pending', 'resuming')" in retention
