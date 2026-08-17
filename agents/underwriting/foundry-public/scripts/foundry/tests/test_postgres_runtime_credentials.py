from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

HELPER_PATH = Path(__file__).parents[1] / "postgres_runtime_credentials.py"
SPEC = importlib.util.spec_from_file_location("postgres_runtime_credentials", HELPER_PATH)
assert SPEC and SPEC.loader
credentials = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(credentials)


class PostgresRuntimeCredentialTests(unittest.TestCase):
    def test_provision_sql_grants_only_runtime_objects(self) -> None:
        sql = credentials.build_provision_sql(
            "underwriting",
            "underwriting_runtime",
            "Password!with'quote",
            "pgadmin",
        )

        self.assertIn("NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT NOBYPASSRLS", sql)
        self.assertIn("CONNECTION LIMIT 50", sql)
        self.assertIn('REASSIGN OWNED BY "underwriting_runtime" TO "pgadmin"', sql)
        self.assertIn('DROP OWNED BY "underwriting_runtime"', sql)
        self.assertIn("REVOKE CREATE ON SCHEMA public FROM PUBLIC", sql)
        self.assertIn('GRANT USAGE ON SCHEMA public TO "underwriting_runtime"', sql)
        self.assertNotIn("GRANT USAGE, CREATE ON SCHEMA", sql)
        self.assertNotIn("GRANT CONNECT, CREATE", sql)
        self.assertNotIn("ON ALL TABLES IN SCHEMA public TO", sql)
        self.assertNotIn("ON ALL SEQUENCES IN SCHEMA public TO", sql)
        self.assertIn(
            'GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public."workflow_runs"',
            sql,
        )
        self.assertIn('public."workflow_checkpoints"', sql)
        self.assertIn('public."checkpoint_writes"', sql)
        self.assertIn(
            'GRANT SELECT ON TABLE public."checkpoint_migrations" TO "underwriting_runtime"',
            sql,
        )
        self.assertIn('GRANT USAGE ON SEQUENCE public."business_state_id_seq"', sql)
        self.assertNotIn("GRANT USAGE, SELECT, UPDATE ON SEQUENCE", sql)

    def test_runtime_url_encodes_credential_and_requires_tls(self) -> None:
        url = credentials.build_runtime_url(
            "underwriting",
            "underwriting_runtime",
            "Password!/@:? #",
            "server.postgres.database.azure.com",
        )
        parsed = urlsplit(url)

        self.assertEqual(parsed.scheme, "postgresql+psycopg")
        self.assertEqual(parsed.hostname, "server.postgres.database.azure.com")
        self.assertEqual(unquote(parsed.username or ""), "underwriting_runtime")
        self.assertEqual(unquote(parsed.password or ""), "Password!/@:? #")
        self.assertEqual(unquote(parsed.path.lstrip("/")), "underwriting")
        self.assertEqual(parse_qs(parsed.query), {"sslmode": ["require"]})

    def test_verification_checks_runtime_access_and_admin_denial(self) -> None:
        sql = credentials.build_verification_sql("underwriting_runtime")

        self.assertIn("PERFORM 1 FROM public.workflow_runs LIMIT 1", sql)
        self.assertIn("CREATE TABLE public.__underwriting_runtime_ddl_probe", sql)
        self.assertIn("CREATE ROLE __underwriting_runtime_role_probe NOLOGIN", sql)
        self.assertIn("WHEN insufficient_privilege THEN NULL", sql)
        self.assertIn("has_table_privilege(current_user, 'public.workflow_events', 'DELETE')", sql)
        self.assertIn(
            "has_table_privilege(current_user, 'public.checkpoint_migrations', 'SELECT')",
            sql,
        )


if __name__ == "__main__":
    unittest.main()
