from __future__ import annotations

from pathlib import Path

import pytest
from app.core.database import PostgresDatabase, postgres_pool_config


def test_database_url_normalizes_psycopg_dialect(monkeypatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg://user:password@server.postgres.database.azure.com:5432/"
        "order_resolution?sslmode=require",
    )

    assert "postgresql+psycopg" not in PostgresDatabase().database_url


def test_foundry_private_runtime_rejects_unresolved_connection_placeholder(
    monkeypatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "foundry-private-hosted")
    monkeypatch.setenv("DB_SCHEMA_MANAGED_EXTERNALLY", "true")
    monkeypatch.setenv(
        "DATABASE_URL",
        "${{connections.orderresolutionruntimesecrets.credentials.database_url}}",
    )

    with pytest.raises(RuntimeError, match="unresolved Foundry project connection placeholder"):
        _ = PostgresDatabase().database_url


def test_foundry_private_runtime_requires_tls(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "foundry-private-wrapper")
    monkeypatch.setenv("DB_SCHEMA_MANAGED_EXTERNALLY", "true")
    monkeypatch.setenv(
        "DATABASE_URL",
        "******server.postgres.database.azure.com:5432/order_resolution",
    )

    with pytest.raises(RuntimeError, match="must require TLS"):
        _ = PostgresDatabase().database_url


def test_foundry_private_runtime_requires_external_schema_management(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "foundry-private-hosted")
    monkeypatch.setenv("DB_SCHEMA_MANAGED_EXTERNALLY", "false")
    monkeypatch.setenv(
        "DATABASE_URL",
        "******server.postgres.database.azure.com:5432/order_resolution?sslmode=require",
    )

    with pytest.raises(RuntimeError, match="DB_SCHEMA_MANAGED_EXTERNALLY=true"):
        _ = PostgresDatabase().database_url


def test_postgres_pool_config_supports_zero_idle_connections(monkeypatch) -> None:
    monkeypatch.setenv("POSTGRES_POOL_MIN_SIZE", "0")
    monkeypatch.setenv("POSTGRES_POOL_MAX_SIZE", "1")
    monkeypatch.setenv("POSTGRES_POOL_MAX_IDLE_SECONDS", "15")
    monkeypatch.setenv("POSTGRES_APPLICATION_NAME", "order-resolution-private-hosted")

    config = postgres_pool_config()

    assert config.min_size == 0
    assert config.max_size == 1
    assert config.max_idle_seconds == 15
    assert config.application_name == "order-resolution-private-hosted"


def test_postgres_pool_config_rejects_maximum_below_minimum(monkeypatch) -> None:
    monkeypatch.setenv("POSTGRES_POOL_MIN_SIZE", "2")
    monkeypatch.setenv("POSTGRES_POOL_MAX_SIZE", "1")

    with pytest.raises(
        ValueError,
        match="POSTGRES_POOL_MAX_SIZE must be at least POSTGRES_POOL_MIN_SIZE",
    ):
        postgres_pool_config()


def test_database_applies_bounded_pool_config(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class _Pool:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        def close(self):
            return None

    monkeypatch.setenv("POSTGRES_POOL_MIN_SIZE", "0")
    monkeypatch.setenv("POSTGRES_POOL_MAX_SIZE", "2")
    monkeypatch.setenv("POSTGRES_POOL_MAX_IDLE_SECONDS", "15")
    monkeypatch.setenv("POSTGRES_APPLICATION_NAME", "order-resolution-private-wrapper")
    monkeypatch.setattr("app.core.database.ConnectionPool", _Pool)

    database = PostgresDatabase()
    database.get_pool()

    assert captured["min_size"] == 0
    assert captured["max_size"] == 2
    assert captured["max_idle"] == 15
    connection_kwargs = captured["kwargs"]
    assert isinstance(connection_kwargs, dict)
    assert connection_kwargs["application_name"] == "order-resolution-private-wrapper"


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
