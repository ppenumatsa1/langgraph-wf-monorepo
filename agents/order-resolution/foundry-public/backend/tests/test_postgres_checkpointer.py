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
