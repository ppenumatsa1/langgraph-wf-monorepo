from __future__ import annotations

from sqlalchemy import create_engine, delete, inspect
from sqlalchemy.engine import Engine

from app.core.config import Settings
from app.infrastructure.db.tables import (
    business_state,
    idempotency_keys,
    metadata,
    underwriting_results,
    workflow_checkpoints,
    workflow_events,
    workflow_runs,
)


def create_db_engine(settings: Settings) -> Engine:
    return create_engine(settings.db_url, future=True, pool_pre_ping=True)


def init_db(engine: Engine, *, schema_managed_externally: bool = False) -> None:
    if schema_managed_externally:
        assert_schema_ready(engine)
        return
    metadata.create_all(engine)


def assert_schema_ready(engine: Engine) -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    missing_tables = sorted(set(metadata.tables) - existing_tables)
    if missing_tables:
        raise RuntimeError(
            "Externally managed database schema is not ready; missing tables: "
            + ", ".join(missing_tables)
        )


def reset_db(engine: Engine) -> None:
    with engine.begin() as conn:
        for table in [
            workflow_events,
            underwriting_results,
            business_state,
            workflow_checkpoints,
            idempotency_keys,
            workflow_runs,
        ]:
            conn.execute(delete(table))
