from __future__ import annotations

import asyncio
from typing import Any, Protocol

from app.core.database import postgres_pool_config
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


class CheckpointerFactory(Protocol):
    async def get(self) -> Any: ...

    async def close(self) -> None: ...


class PostgresCheckpointerFactory:
    """Own one process-lifetime async pool and LangGraph saver."""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._pool: AsyncConnectionPool | None = None
        self._saver: AsyncPostgresSaver | None = None
        self._lock = asyncio.Lock()

    async def get(self) -> AsyncPostgresSaver:
        if self._saver is not None:
            return self._saver
        async with self._lock:
            if self._saver is not None:
                return self._saver
            config = postgres_pool_config()
            pool = AsyncConnectionPool(
                conninfo=self._database_url,
                min_size=config.min_size,
                max_size=config.max_size,
                max_idle=config.max_idle_seconds,
                open=False,
                kwargs={
                    "application_name": config.application_name,
                    "autocommit": True,
                    "prepare_threshold": 0,
                    "row_factory": dict_row,
                },
            )
            await pool.open(wait=True)
            self._pool = pool
            self._saver = AsyncPostgresSaver(pool)
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


class StaticCheckpointerFactory:
    def __init__(self, checkpointer: Any) -> None:
        self._checkpointer = checkpointer

    async def get(self) -> Any:
        return self._checkpointer

    async def close(self) -> None:
        return None
