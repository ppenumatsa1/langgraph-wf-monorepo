from __future__ import annotations

import importlib.util
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

HELPER_PATH = Path(__file__).parents[1] / "postgres_runtime_credentials.py"
SPEC = importlib.util.spec_from_file_location("postgres_runtime_credentials", HELPER_PATH)
assert SPEC and SPEC.loader
credentials = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(credentials)


def test_provision_sql_is_limited_to_runtime_objects() -> None:
    sql = credentials.build_provision_sql(
        "order_resolution",
        "order_resolution_runtime",
        "Password!with'quote",
        "pgadmin",
    )
    assert "NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT NOBYPASSRLS" in sql
    assert 'REASSIGN OWNED BY "order_resolution_runtime" TO "pgadmin"' in sql
    assert "REVOKE CREATE ON SCHEMA public FROM PUBLIC" in sql
    assert 'public."workflow_runs"' in sql
    assert 'public."responses_dispatches"' in sql
    assert 'public."eval_results" TO "order_resolution_runtime"' in sql
    assert 'GRANT USAGE ON SEQUENCE public."conversation_messages_id_seq"' in sql
    assert "ON ALL TABLES IN SCHEMA public TO" not in sql


def test_runtime_url_encodes_secret_and_requires_tls() -> None:
    url = credentials.build_runtime_url(
        "order_resolution",
        "order_resolution_runtime",
        "Password!/@:? #",
        "server.postgres.database.azure.com",
    )
    parsed = urlsplit(url)
    assert parsed.scheme == "postgresql+psycopg"
    assert parsed.hostname == "server.postgres.database.azure.com"
    assert unquote(parsed.username or "") == "order_resolution_runtime"
    assert unquote(parsed.password or "") == "Password!/@:? #"
    assert unquote(parsed.path.lstrip("/")) == "order_resolution"
    assert parse_qs(parsed.query) == {"sslmode": ["require"]}


def test_verification_denies_runtime_ddl() -> None:
    sql = credentials.build_verification_sql("order_resolution_runtime")
    assert "PERFORM 1 FROM public.workflow_runs LIMIT 1" in sql
    assert "CREATE TABLE public.__order_resolution_runtime_ddl_probe" in sql
    assert "CREATE ROLE __order_resolution_runtime_role_probe NOLOGIN" in sql
    assert "WHEN insufficient_privilege THEN NULL" in sql
    assert "public.responses_dispatches', 'DELETE'" in sql
