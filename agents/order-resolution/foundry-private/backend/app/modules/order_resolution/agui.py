from __future__ import annotations

import hashlib
import json
import re
from typing import Any
from uuid import UUID

from app.modules.order_resolution import events as event_types
from app.modules.order_resolution.models import WorkflowEvent

_THREAD_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_STEP_NAMES = {"triage", "policy_retrieval", "resolution", "explanation"}
_TOOL_NAMES = {
    "fetch_order_status/fetch_policy": "policy-lookup",
    "search": "knowledge-search",
}
_TERMINAL_STATUSES = {"completed", "escalated", "failed"}
_HITL_DECISIONS = {"approve", "reject"}


def is_safe_thread_id(thread_id: str) -> bool:
    """Return whether an opaque selected-thread identifier is safe to expose."""

    return bool(_THREAD_ID_PATTERN.fullmatch(thread_id))


def encode_agui_sse(event: dict[str, Any]) -> str:
    """Encode one native AG-UI event using the protocol's SSE data framing."""

    return f"data: {json.dumps(event, separators=(',', ':'))}\n\n"


def agui_run_started_event(thread_id: str) -> dict[str, str]:
    return {"type": "RUN_STARTED", "threadId": thread_id, "runId": thread_id}


def native_agui_events_for_workflow_event(event: WorkflowEvent) -> list[dict[str, Any]]:
    """Project a durable native event into a deliberately minimal AG-UI view.

    This is a display-only projection. It never passes workflow payloads,
    prompts, tool arguments/results, policy data, order data, or checkpoint
    state through to an AG-UI/CopilotKit client.
    """

    if not is_safe_thread_id(event.thread_id):
        return []

    event_id = _safe_event_id(event.id)
    if event.type == event_types.WORKFLOW_STAGE:
        return _stage_events(event)
    if event.type == event_types.TOOL_CALL:
        return _tool_events(event, event_id)
    if event.type == event_types.CHECKPOINT_CREATED:
        return [_checkpoint_event(event)]
    if event.type == event_types.HITL_REQUEST:
        return [_hitl_request_event(event)]
    if event.type == event_types.HITL_RESPONSE:
        return _hitl_response_events(event)
    if event.type == event_types.WORKFLOW_OUTPUT:
        return _output_events(event, event_id)
    if event.type == event_types.WORKFLOW_FAILED:
        return [
            {
                "type": "RUN_ERROR",
                "message": "The resolution workflow could not be completed.",
                "code": "workflow_failed",
            }
        ]
    return []


def _safe_event_id(event_id: str) -> str:
    try:
        return str(UUID(event_id))
    except ValueError:
        return hashlib.sha256(event_id.encode()).hexdigest()[:32]


def _stage_events(event: WorkflowEvent) -> list[dict[str, Any]]:
    agent = event.payload.get("agent")
    status = event.payload.get("status")
    if not isinstance(agent, str) or agent not in _STEP_NAMES or not isinstance(status, str):
        return []
    if status == "started":
        return [{"type": "STEP_STARTED", "stepName": agent}]
    if status in {"completed", "failed", "skipped"}:
        return [{"type": "STEP_FINISHED", "stepName": agent}]
    return []


def _tool_events(event: WorkflowEvent, event_id: str) -> list[dict[str, Any]]:
    local_tool = event.payload.get("local_tool")
    mcp_tool = event.payload.get("mcp_tool")
    tool_name = (_TOOL_NAMES.get(local_tool) if isinstance(local_tool, str) else None) or (
        _TOOL_NAMES.get(mcp_tool) if isinstance(mcp_tool, str) else None
    )
    if tool_name is None:
        return []

    tool_call_id = f"{event_id}:tool"
    return [
        {
            "type": "TOOL_CALL_START",
            "toolCallId": tool_call_id,
            "toolCallName": tool_name,
        },
        {
            "type": "TOOL_CALL_RESULT",
            "toolCallId": tool_call_id,
            "messageId": event_id,
            "content": {"status": "completed"},
        },
        {"type": "TOOL_CALL_END", "toolCallId": tool_call_id},
    ]


def _checkpoint_event(event: WorkflowEvent) -> dict[str, Any]:
    value = {"status": "created"}
    checkpoint_id = _safe_checkpoint_id(event.payload.get("checkpoint_id"))
    if checkpoint_id:
        value["checkpointId"] = checkpoint_id
    return {
        "type": "CUSTOM",
        "name": "order-resolution.checkpoint-created",
        "value": value,
    }


def _hitl_request_event(event: WorkflowEvent) -> dict[str, Any]:
    value = {"status": "pending"}
    checkpoint_id = _safe_checkpoint_id(event.payload.get("checkpoint_id"))
    if checkpoint_id:
        value["checkpointId"] = checkpoint_id
    return {
        "type": "CUSTOM",
        "name": "order-resolution.approval-required",
        "value": value,
    }


def _hitl_response_events(event: WorkflowEvent) -> list[dict[str, Any]]:
    decision = event.payload.get("decision")
    if not isinstance(decision, str) or decision not in _HITL_DECISIONS:
        return []

    value = {"decision": decision}
    checkpoint_id = _safe_checkpoint_id(event.payload.get("checkpoint_id"))
    if checkpoint_id:
        value["checkpointId"] = checkpoint_id
    return [
        {
            "type": "CUSTOM",
            "name": "order-resolution.approval-resolved",
            "value": value,
        }
    ]


def _output_events(event: WorkflowEvent, event_id: str) -> list[dict[str, Any]]:
    status = event.payload.get("status")
    safe_status = (
        status if isinstance(status, str) and status in _TERMINAL_STATUSES else "completed"
    )
    message = {
        "completed": "The resolution workflow completed.",
        "escalated": "The resolution workflow was escalated for human support.",
        "failed": "The resolution workflow could not be completed.",
    }[safe_status]

    return [
        {
            "type": "TEXT_MESSAGE_START",
            "messageId": event_id,
            "role": "assistant",
        },
        {
            "type": "TEXT_MESSAGE_CONTENT",
            "messageId": event_id,
            "delta": message,
        },
        {"type": "TEXT_MESSAGE_END", "messageId": event_id},
        {
            "type": "RUN_FINISHED",
            "threadId": event.thread_id,
            "runId": event.thread_id,
        },
    ]


def _safe_checkpoint_id(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return str(UUID(value))
    except ValueError:
        return None


__all__ = [
    "agui_run_started_event",
    "encode_agui_sse",
    "is_safe_thread_id",
    "native_agui_events_for_workflow_event",
]
