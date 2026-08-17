#!/usr/bin/env python3
"""Build credential-provisioning SQL without logging secret values."""

from __future__ import annotations

import os
import sys
from urllib.parse import quote

RUNTIME_TABLES = (
    "workflow_runs",
    "business_state",
    "underwriting_results",
    "workflow_events",
    "idempotency_keys",
    "workflow_checkpoints",
    "checkpoints",
    "checkpoint_blobs",
    "checkpoint_writes",
)
RUNTIME_READ_ONLY_TABLES = ("checkpoint_migrations",)
RUNTIME_SEQUENCES = (
    "business_state_id_seq",
    "underwriting_results_id_seq",
    "workflow_events_id_seq",
)
RUNTIME_CONNECTION_LIMIT = 50


def quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def quote_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _qualified_names(names: tuple[str, ...]) -> str:
    return ", ".join(f"public.{quote_identifier(name)}" for name in names)


def build_provision_sql(
    database: str,
    runtime_username: str,
    hosted_password: str,
    admin_username: str,
) -> str:
    database_identifier = quote_identifier(database)
    role_identifier = quote_identifier(runtime_username)
    role_literal = quote_literal(runtime_username)
    password_literal = quote_literal(hosted_password)
    admin_identifier = quote_identifier(admin_username)
    tables = _qualified_names(RUNTIME_TABLES)
    read_only_tables = _qualified_names(RUNTIME_READ_ONLY_TABLES)
    sequences = _qualified_names(RUNTIME_SEQUENCES)

    return f"""DO $provision$
DECLARE
  granted_role name;
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = {role_literal}) THEN
    EXECUTE format(
      'CREATE ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT NOBYPASSRLS CONNECTION LIMIT {RUNTIME_CONNECTION_LIMIT} PASSWORD %L',
      {role_literal},
      {password_literal}
    );
  ELSE
    EXECUTE format(
      'ALTER ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT NOBYPASSRLS CONNECTION LIMIT {RUNTIME_CONNECTION_LIMIT} PASSWORD %L',
      {role_literal},
      {password_literal}
    );
  END IF;

  FOR granted_role IN
    SELECT parent.rolname
    FROM pg_auth_members membership
    JOIN pg_roles member ON member.oid = membership.member
    JOIN pg_roles parent ON parent.oid = membership.roleid
    WHERE member.rolname = {role_literal}
  LOOP
    EXECUTE format('REVOKE %I FROM %I', granted_role, {role_literal});
  END LOOP;
END
$provision$;
REASSIGN OWNED BY {role_identifier} TO {admin_identifier};
DROP OWNED BY {role_identifier};
REVOKE ALL PRIVILEGES ON DATABASE {database_identifier} FROM {role_identifier};
GRANT CONNECT ON DATABASE {database_identifier} TO {role_identifier};
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL PRIVILEGES ON SCHEMA public FROM {role_identifier};
GRANT USAGE ON SCHEMA public TO {role_identifier};
REVOKE ALL PRIVILEGES ON ALL TABLES IN SCHEMA public FROM {role_identifier};
REVOKE ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public FROM {role_identifier};
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE {tables} TO {role_identifier};
GRANT SELECT ON TABLE {read_only_tables} TO {role_identifier};
GRANT USAGE ON SEQUENCE {sequences} TO {role_identifier};"""


def build_runtime_url(
    database: str,
    runtime_username: str,
    hosted_password: str,
    server_fqdn: str,
) -> str:
    username = quote(runtime_username, safe="")
    password = quote(hosted_password, safe="")
    database_name = quote(database, safe="")
    return (
        f"postgresql+psycopg://{username}:{password}@{server_fqdn}:5432/"
        f"{database_name}?sslmode=require"
    )


def build_verification_sql(runtime_username: str) -> str:
    role_literal = quote_literal(runtime_username)
    table_checks = "\n  ".join(
        (
            f"IF NOT has_table_privilege(current_user, 'public.{table}', 'SELECT')"
            f" OR NOT has_table_privilege(current_user, 'public.{table}', 'INSERT')"
            f" OR NOT has_table_privilege(current_user, 'public.{table}', 'UPDATE')"
            f" OR NOT has_table_privilege(current_user, 'public.{table}', 'DELETE') THEN\n"
            f"    RAISE EXCEPTION 'Runtime credential is missing required table privileges.';\n"
            f"  END IF;"
        )
        for table in RUNTIME_TABLES
    )
    sequence_checks = "\n  ".join(
        (
            f"IF NOT has_sequence_privilege(current_user, 'public.{sequence}', 'USAGE') THEN\n"
            f"    RAISE EXCEPTION 'Runtime credential is missing required sequence privileges.';\n"
            f"  END IF;"
        )
        for sequence in RUNTIME_SEQUENCES
    )
    read_only_checks = "\n  ".join(
        (
            f"IF NOT has_table_privilege(current_user, 'public.{table}', 'SELECT')"
            f" OR has_table_privilege(current_user, 'public.{table}', 'INSERT')"
            f" OR has_table_privilege(current_user, 'public.{table}', 'UPDATE')"
            f" OR has_table_privilege(current_user, 'public.{table}', 'DELETE') THEN\n"
            f"    RAISE EXCEPTION 'Runtime credential has invalid read-only table privileges.';\n"
            f"  END IF;"
        )
        for table in RUNTIME_READ_ONLY_TABLES
    )

    return f"""DO $verify$
DECLARE
  role_attributes record;
BEGIN
  IF current_user <> {role_literal} THEN
    RAISE EXCEPTION 'Runtime credential authenticated as an unexpected database role.';
  END IF;

  SELECT rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls, rolinherit
  INTO role_attributes
  FROM pg_roles
  WHERE rolname = current_user;
  IF role_attributes.rolsuper OR role_attributes.rolcreatedb
     OR role_attributes.rolcreaterole OR role_attributes.rolreplication
     OR role_attributes.rolbypassrls OR role_attributes.rolinherit THEN
    RAISE EXCEPTION 'Runtime credential has prohibited role attributes.';
  END IF;
  IF EXISTS (
    SELECT 1
    FROM pg_auth_members membership
    WHERE membership.member = (SELECT oid FROM pg_roles WHERE rolname = current_user)
  ) THEN
    RAISE EXCEPTION 'Runtime credential has prohibited role membership.';
  END IF;
  IF NOT has_schema_privilege(current_user, 'public', 'USAGE')
     OR has_schema_privilege(current_user, 'public', 'CREATE') THEN
    RAISE EXCEPTION 'Runtime credential has invalid public schema privileges.';
  END IF;

  {table_checks}
  {read_only_checks}
  {sequence_checks}

  PERFORM 1 FROM public.workflow_runs LIMIT 1;

  BEGIN
    EXECUTE 'CREATE TABLE public.__underwriting_runtime_ddl_probe (id integer)';
    RAISE EXCEPTION 'Runtime credential can create schema objects.';
  EXCEPTION
    WHEN insufficient_privilege THEN NULL;
  END;

  BEGIN
    EXECUTE 'CREATE ROLE __underwriting_runtime_role_probe NOLOGIN';
    RAISE EXCEPTION 'Runtime credential can create database roles.';
  EXCEPTION
    WHEN insufficient_privilege THEN NULL;
  END;
END
$verify$;"""


def required_env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise ValueError(f"Missing required environment value: {name}")
    return value


def main() -> int:
    if len(sys.argv) != 2:
        raise ValueError("Expected one operation: provision, runtime-url, or verify")

    operation = sys.argv[1]
    database = required_env("POSTGRES_DATABASE")
    runtime_username = required_env("POSTGRES_RUNTIME_USERNAME")

    if operation == "provision":
        print(
            build_provision_sql(
                database,
                runtime_username,
                required_env("POSTGRES_HOSTED_PASSWORD"),
                required_env("POSTGRES_ADMIN_USERNAME"),
            )
        )
    elif operation == "runtime-url":
        print(
            build_runtime_url(
                database,
                runtime_username,
                required_env("POSTGRES_HOSTED_PASSWORD"),
                required_env("POSTGRES_SERVER_FQDN"),
            )
        )
    elif operation == "verify":
        print(build_verification_sql(runtime_username))
    else:
        raise ValueError("Expected one operation: provision, runtime-url, or verify")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as error:
        print(error, file=sys.stderr)
        raise SystemExit(2) from None
