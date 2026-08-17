#!/usr/bin/env python3
"""Emit idempotent PostgreSQL DDL for the underwriting persistence schema."""

from __future__ import annotations

from app.infrastructure.db.tables import metadata, workflow_runs
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable


def main() -> None:
    dialect = postgresql.dialect()
    statements = [
        str(CreateTable(table, if_not_exists=True).compile(dialect=dialect))
        for table in metadata.sorted_tables
    ]
    statements.extend(
        str(CreateIndex(index, if_not_exists=True).compile(dialect=dialect))
        for table in metadata.sorted_tables
        for index in table.indexes
    )
    statements.append(
        "ALTER TABLE public.workflow_runs ADD COLUMN IF NOT EXISTS applicant_name VARCHAR(256)"
    )
    statements.append(
        "ALTER TABLE public.workflow_runs ADD COLUMN IF NOT EXISTS started_at TIMESTAMP WITH TIME ZONE"
    )
    statements.append(
        "ALTER TABLE public.workflow_runs ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP WITH TIME ZONE"
    )
    statements.append(
        "ALTER TABLE public.workflow_runs ADD COLUMN IF NOT EXISTS duration_ms BIGINT"
    )
    statements.extend(
        str(CreateIndex(index, if_not_exists=True).compile(dialect=dialect))
        for index in workflow_runs.indexes
    )
    print(";\n".join(dict.fromkeys(statements)) + ";")


if __name__ == "__main__":
    main()
