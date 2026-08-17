from __future__ import annotations

import asyncio

from app.core.database import postgres_db
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository
from app.langgraph.checkpointer import PostgresCheckpointerFactory


async def bootstrap() -> None:
    postgres_db.bootstrap_application_schema()
    await PostgresCheckpointerFactory(
        postgres_db.database_url,
        WorkflowRunRepository(),
    ).setup()


if __name__ == "__main__":
    asyncio.run(bootstrap())
