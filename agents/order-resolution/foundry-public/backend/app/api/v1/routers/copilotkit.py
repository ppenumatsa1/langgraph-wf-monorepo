from __future__ import annotations

from collections.abc import AsyncGenerator

from app.api.v1.schemas.copilotkit import (
    CopilotKitAgentDiscovery,
    CopilotKitBridgeRequest,
    CopilotKitDiscoveryResponse,
    CopilotKitThreadEndpoints,
)
from app.core.container import workflow_run_repository
from app.modules.order_resolution.agui import (
    agui_run_started_event,
    encode_agui_sse,
    native_agui_events_for_workflow_event,
)
from app.modules.order_resolution.durable_events import iter_durable_workflow_events
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/copilotkit", tags=["copilotkit"])
_COPILOTKIT_AGENT_ID = "order-resolution-thread-assistant"


def _require_selected_thread(thread_id: str) -> None:
    if workflow_run_repository.get_workflow_run(thread_id) is None:
        raise HTTPException(status_code=404, detail="Selected workflow thread was not found.")


async def _copilotkit_stream(thread_id: str) -> AsyncGenerator[str, None]:
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


@router.get("/info", response_model=CopilotKitDiscoveryResponse)
@router.get("", response_model=CopilotKitDiscoveryResponse)
async def discover_copilotkit_runtime() -> CopilotKitDiscoveryResponse:
    """Return static runtime metadata without reading workflow or user data."""

    return CopilotKitDiscoveryResponse(
        agents={
            _COPILOTKIT_AGENT_ID: CopilotKitAgentDiscovery(
                name="Order Resolution Thread Assistant",
                className="OrderResolutionThreadAssistant",
                description=(
                    "Provides a read-only, redacted durable-event view for a selected workflow "
                    "thread."
                ),
            )
        },
        threadEndpoints=CopilotKitThreadEndpoints(),
    )


@router.post("")
async def stream_selected_thread(request: CopilotKitBridgeRequest) -> StreamingResponse:
    """Provide a read-only, redacted AG-UI projection for one durable thread."""

    _require_selected_thread(request.thread_id)
    return StreamingResponse(
        _copilotkit_stream(request.thread_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
