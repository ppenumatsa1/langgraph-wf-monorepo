from __future__ import annotations

import asyncio
import os

import psycopg
import pytest
from app.core.database import PostgresDatabase

os.environ.setdefault("ENABLE_LANGGRAPH_AUTO_TRACING", "false")


def _database_available() -> bool:
    database_url = os.getenv("DATABASE_URL") or PostgresDatabase().database_url
    try:
        with psycopg.connect(database_url, connect_timeout=2):
            return True
    except Exception:
        return False


TEST_DATABASE_URL = PostgresDatabase().database_url
DATABASE_AVAILABLE = _database_available()

if DATABASE_AVAILABLE:
    from app.core.database import postgres_db
    from app.langgraph.checkpointer import PostgresCheckpointerFactory

    postgres_db.bootstrap_application_schema()
    asyncio.run(PostgresCheckpointerFactory(postgres_db.database_url).setup())


@pytest.fixture(scope="session", autouse=True)
def ensure_database_available() -> None:
    if not DATABASE_AVAILABLE:
        pytest.skip("PostgreSQL is required for backend tests in this repository.")


@pytest.fixture(autouse=True)
def deterministic_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)
    monkeypatch.setenv("ENABLE_TELEMETRY", "false")
    monkeypatch.setenv("VERIFY_DB_SCHEMA_ON_STARTUP", "true")
    for name in (
        "FOUNDRY_PROJECTS_ENDPOINT",
        "FOUNDRY_PROJECT_ENDPOINT",
        "FOUNDRY_MODEL_DEPLOYMENT_NAME",
        "FOUNDRY_MODEL",
        "LANGCHAIN_TRACING_V2",
        "LANGSMITH_TRACING",
    ):
        monkeypatch.delenv(name, raising=False)
