from __future__ import annotations

import json
from uuid import uuid4

import pytest
from app.api.v1.routers.chat import _persisted_sse_stream
from app.infrastructure.persistence import WorkflowRunRepository
from app.modules.order_resolution.models import WorkflowEvent


def _payload(frame: str) -> dict:
    assert frame.startswith("data: ")
    return json.loads(frame.removeprefix("data: ").strip())


async def _next_data(stream) -> str:
    while True:
        frame = await anext(stream)
        if frame.startswith("data: "):
            return frame


@pytest.mark.asyncio
async def test_native_sse_replays_tails_and_reconnects_from_durable_events() -> None:
    repository = WorkflowRunRepository()
    thread_id = str(uuid4())
    repository.create_workflow_run(
        thread_id=thread_id,
        input_text="durable stream validation",
        session_id=thread_id,
    )
    first = WorkflowEvent(
        thread_id=thread_id,
        type="workflow.stage",
        payload={"agent": "triage", "status": "started"},
    )
    repository.append_workflow_event(thread_id, first)

    stream = _persisted_sse_stream(thread_id, rich=False)
    first_frame = await _next_data(stream)
    assert _payload(first_frame)["id"] == first.id

    second = WorkflowEvent(
        thread_id=thread_id,
        type="workflow.output",
        payload={"status": "completed", "message": "done"},
    )
    repository.append_workflow_event(thread_id, second)
    second_frame = await _next_data(stream)
    assert _payload(second_frame)["id"] == second.id
    await stream.aclose()

    cursor = f"{first.timestamp}|{first.id}"
    restarted_stream = _persisted_sse_stream(
        thread_id,
        rich=False,
        initial_cursor=cursor,
    )
    replayed_frame = await _next_data(restarted_stream)
    assert _payload(replayed_frame)["id"] == second.id
    heartbeat = await anext(restarted_stream)
    assert heartbeat == ": ping\n\n"
    await restarted_stream.aclose()
