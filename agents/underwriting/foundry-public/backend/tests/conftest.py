from __future__ import annotations

import asyncio
import os
from urllib.parse import urlsplit, urlunsplit

import psycopg
import pytest

from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository
from app.langgraph.checkpointer import PostgresCheckpointerFactory

TEST_DATABASE_NAME = "underwriting_langgraph_test"
ADMIN_DATABASE_URL = os.getenv(
    "UNDERWRITING_TEST_ADMIN_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5433/postgres?sslmode=disable",
)


def _replace_path(url: str, database_name: str) -> str:
    parsed = urlsplit(url)
    return urlunsplit(
        (parsed.scheme, parsed.netloc, f"/{database_name}", parsed.query, parsed.fragment)
    )


def _database_available() -> bool:
    try:
        with psycopg.connect(ADMIN_DATABASE_URL, connect_timeout=2, autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM pg_database WHERE datname = %s",
                    (TEST_DATABASE_NAME,),
                )
                exists = cur.fetchone() is not None
                if not exists:
                    cur.execute(f"CREATE DATABASE {TEST_DATABASE_NAME}")
        with psycopg.connect(TEST_DATABASE_URL, connect_timeout=2):
            return True
    except Exception:
        return False


TEST_DATABASE_URL = _replace_path(ADMIN_DATABASE_URL, TEST_DATABASE_NAME)
DATABASE_AVAILABLE = _database_available()

if DATABASE_AVAILABLE:
    os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)
    from app.core.database import postgres_db

    postgres_db.bootstrap_application_schema()
    asyncio.run(
        PostgresCheckpointerFactory(postgres_db.database_url, WorkflowRunRepository()).setup()
    )


@pytest.fixture(scope="session", autouse=True)
def ensure_database_available() -> None:
    if not DATABASE_AVAILABLE:
        pytest.skip("PostgreSQL is required for backend tests in this repository.")


@pytest.fixture(autouse=True)
def deterministic_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("VERIFY_DB_SCHEMA_ON_STARTUP", "true")
    monkeypatch.setenv("UNDERWRITING_EXECUTION_MODE", "local")
    monkeypatch.setenv("ENABLE_TELEMETRY", "false")
    import foundry.main as hosted_main
    from app.core import container

    container.get_settings.cache_clear()
    container.get_underwriting_service.cache_clear()
    container.get_copilot_bridge.cache_clear()
    hosted_main._local_service.cache_clear()
    WorkflowRunRepository().reset_all()
