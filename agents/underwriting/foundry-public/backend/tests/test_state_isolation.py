from __future__ import annotations

import asyncio

from app.core.database import postgres_db
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository
from app.langgraph.checkpointer import PostgresCheckpointerFactory


def test_checkpointer_factory_reuses_async_pool_until_closed() -> None:
    async def exercise() -> None:
        repository = WorkflowRunRepository()
        factory = PostgresCheckpointerFactory(postgres_db.database_url, repository)
        first = await factory.get()
        second = await factory.get()
        assert first is second
        await factory.close()
        third = await factory.get()
        assert third is not first
        await factory.close()

    asyncio.run(exercise())
