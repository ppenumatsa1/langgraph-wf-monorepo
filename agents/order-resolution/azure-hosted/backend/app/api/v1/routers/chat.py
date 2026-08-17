from __future__ import annotations

import json
from collections.abc import AsyncGenerator

from app.api.v1.schemas.chat import ChatRunRequest, ChatRunResponse
from app.core.container import order_resolution_service, workflow_run_repository
from app.modules.order_resolution.agui import (
    agui_run_started_event,
    encode_agui_sse,
    is_safe_thread_id,
    native_agui_events_for_workflow_event,
)
from app.modules.order_resolution.durable_events import iter_durable_workflow_events
from app.modules.order_resolution.models import (
    ConcurrentStartError,
    PendingApprovalError,
)
from app.modules.order_resolution.rich_events import rich_envelope_for_workflow_event
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/chat", tags=["chat"])


async def _persisted_sse_stream(
    thread_id: str,
    *,
    rich: bool,
    initial_cursor: str | None = None,
) -> AsyncGenerator[str, None]:
    sequence = 0
    run_started = False
    async for event in iter_durable_workflow_events(
        thread_id,
        workflow_run_repository.list_workflow_events,
        initial_cursor=initial_cursor,
        emit_heartbeats=True,
    ):
        if event is None:
            yield ": ping\n\n"
            continue
        if rich:
            sequence += 1
            envelope = rich_envelope_for_workflow_event(event, sequence)
            if not run_started:
                envelope["events"].insert(
                    0,
                    {
                        "type": "RUN_STARTED",
                        "threadId": event.thread_id,
                        "runId": event.payload.get("workflow_run_id") or event.thread_id,
                        "timestamp": envelope.get("events", [{}])[0].get("timestamp"),
                        "rawEvent": event.model_dump(),
                    },
                )
                run_started = True
            yield f"event: workflow.rich\ndata: {json.dumps(envelope, default=str)}\n\n"
        else:
            yield f"data: {event.model_dump_json()}\n\n"


def _require_selected_thread(thread_id: str) -> None:
    if (
        not is_safe_thread_id(thread_id)
        or workflow_run_repository.get_workflow_run(thread_id) is None
    ):
        raise HTTPException(status_code=404, detail="Selected workflow thread was not found.")


async def _agui_stream(thread_id: str) -> AsyncGenerator[str, None]:
    yield encode_agui_sse(agui_run_started_event(thread_id))
    async for workflow_event in iter_durable_workflow_events(
        thread_id,
        workflow_run_repository.list_workflow_events,
        emit_heartbeats=True,
    ):
        if workflow_event is None:
            yield ": ping\n\n"
            continue
        for event in native_agui_events_for_workflow_event(workflow_event):
            yield encode_agui_sse(event)


@router.post("/run", response_model=ChatRunResponse)
async def run_chat(request: ChatRunRequest) -> ChatRunResponse:
    try:
        return await order_resolution_service.start_chat_run(request)
    except (PendingApprovalError, ConcurrentStartError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/stream/{thread_id}")
async def stream_chat(
    thread_id: str,
    cursor: str | None = None,
) -> StreamingResponse:
    return StreamingResponse(
        _persisted_sse_stream(
            thread_id,
            rich=False,
            initial_cursor=cursor,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/stream/{thread_id}/rich")
async def stream_chat_rich(thread_id: str) -> StreamingResponse:
    return StreamingResponse(
        _persisted_sse_stream(thread_id, rich=True),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/stream/{thread_id}/ag-ui")
async def stream_chat_agui(thread_id: str) -> StreamingResponse:
    _require_selected_thread(thread_id)
    return StreamingResponse(
        _agui_stream(thread_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
