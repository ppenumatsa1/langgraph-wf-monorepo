from __future__ import annotations

from typing import TypedDict
from uuid import uuid4

import pytest
from app.core.database import postgres_db
from app.langgraph.checkpointer import PostgresCheckpointerFactory
from langgraph.graph import END, START, StateGraph


class _State(TypedDict, total=False):
    value: int


@pytest.mark.asyncio
async def test_async_postgres_checkpointer_applies_bounded_pool_config(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    class _Pool:
        def __init__(self, **kwargs):
            captured.update(kwargs)

        async def open(self, *, wait):
            captured["wait"] = wait

        async def close(self):
            return None

    class _Saver:
        def __init__(self, pool):
            captured["saver_pool"] = pool

    monkeypatch.setenv("POSTGRES_POOL_MIN_SIZE", "0")
    monkeypatch.setenv("POSTGRES_POOL_MAX_SIZE", "1")
    monkeypatch.setenv("POSTGRES_POOL_MAX_IDLE_SECONDS", "15")
    monkeypatch.setenv("POSTGRES_APPLICATION_NAME", "order-resolution-private-hosted")
    monkeypatch.setattr("app.langgraph.checkpointer.AsyncConnectionPool", _Pool)
    monkeypatch.setattr("app.langgraph.checkpointer.AsyncPostgresSaver", _Saver)

    factory = PostgresCheckpointerFactory("******localhost/test")
    await factory.get()
    await factory.close()

    assert captured["min_size"] == 0
    assert captured["max_size"] == 1
    assert captured["max_idle"] == 15
    connection_kwargs = captured["kwargs"]
    assert isinstance(connection_kwargs, dict)
    assert connection_kwargs["application_name"] == "order-resolution-private-hosted"
    assert captured["wait"] is True


@pytest.mark.asyncio
async def test_async_postgres_checkpointer_persists_graph_state() -> None:
    thread_id = str(uuid4())
    factory = PostgresCheckpointerFactory(postgres_db.database_url)
    builder = StateGraph(_State)
    builder.add_node("increment", lambda state: {"value": state["value"] + 1})
    builder.add_edge(START, "increment")
    builder.add_edge("increment", END)
    config = {"configurable": {"thread_id": thread_id}}

    saver = await factory.get()
    graph = builder.compile(checkpointer=saver)
    assert (await graph.ainvoke({"value": 1}, config))["value"] == 2
    assert await factory.get() is saver

    recompiled = builder.compile(checkpointer=saver)
    snapshot = await recompiled.aget_state(config)
    await factory.close()

    assert snapshot.values["value"] == 2
    assert snapshot.config["configurable"]["checkpoint_id"]
