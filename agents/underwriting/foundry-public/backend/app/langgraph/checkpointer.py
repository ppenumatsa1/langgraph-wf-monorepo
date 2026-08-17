from __future__ import annotations

import asyncio
import os
from typing import Any, Protocol

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from app.infrastructure.persistence.checkpoint_store import TracingAsyncPostgresSaver
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository


class CheckpointerFactory(Protocol):
    async def get(self) -> Any: ...

    async def close(self) -> None: ...


class PostgresCheckpointerFactory:
    def __init__(self, database_url: str, repository: WorkflowRunRepository) -> None:
        self._database_url = database_url
        self._repository = repository
        self._pool: AsyncConnectionPool | None = None
        self._saver: TracingAsyncPostgresSaver | None = None
        self._lock = asyncio.Lock()

    async def get(self) -> TracingAsyncPostgresSaver:
        if self._saver is not None:
            return self._saver
        async with self._lock:
            if self._saver is not None:
                return self._saver
            pool = AsyncConnectionPool(
                conninfo=self._database_url,
                min_size=max(1, int(os.getenv("LANGGRAPH_POOL_MIN_SIZE", "1"))),
                max_size=max(1, int(os.getenv("LANGGRAPH_POOL_MAX_SIZE", "10"))),
                open=False,
                kwargs={
                    "autocommit": True,
                    "prepare_threshold": 0,
                    "row_factory": dict_row,
                },
            )
            await pool.open(wait=True)
            serde = JsonPlusSerializer(
                pickle_fallback=False,
                allowed_msgpack_modules=None,
            )
            saver = TracingAsyncPostgresSaver(pool, self._repository, serde=serde)
            self._pool = pool
            self._saver = saver
            return self._saver

    async def setup(self) -> None:
        saver = await self.get()
        try:
            await saver.setup()
        finally:
            await self.close()

    async def close(self) -> None:
        async with self._lock:
            pool = self._pool
            self._pool = None
            self._saver = None
        if pool is not None:
            await pool.close()
