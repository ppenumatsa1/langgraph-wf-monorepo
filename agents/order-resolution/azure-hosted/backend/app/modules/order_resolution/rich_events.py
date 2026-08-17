from __future__ import annotations

from typing import Any

from app.modules.order_resolution import events as event_types
from app.modules.order_resolution.models import WorkflowEvent

AGUI_VERSION = "ag-ui-compatible.v1"


def _timestamp_ms(timestamp: str) -> int | None:
    from datetime import datetime

    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return None
    return int(parsed.timestamp() * 1000)


def _step_status(event: WorkflowEvent) -> str:
    status = event.payload.get("status")
    return status if isinstance(status, str) else "completed"


def _run_id(event: WorkflowEvent) -> str:
    run_id = event.payload.get("workflow_run_id") or event.payload.get("run_id")
    return str(run_id) if run_id else event.thread_id


def _custom_event(event: WorkflowEvent, name: str, value: dict[str, Any]) -> dict[str, Any]:
    return {
        "type": "CUSTOM",
        "name": name,
        "value": value,
    }


def rich_events_for_workflow_event(event: WorkflowEvent) -> list[dict[str, Any]]:
    """Project native workflow events to AG-UI-compatible rich events.

    Existing native events stay the source of truth. This adapter is additive so
    current SSE consumers and persisted workflow history remain stable.
    """

    run_id = _run_id(event)
    timestamp = _timestamp_ms(event.timestamp)
    common = {
        "threadId": event.thread_id,
        "runId": run_id,
        "timestamp": timestamp,
        "rawEvent": event.model_dump(),
    }

    if event.type == event_types.WORKFLOW_STAGE:
        step_name = str(event.payload.get("agent") or "workflow")
        status = _step_status(event)
        rich_type = "STEP_STARTED" if status == "started" else "STEP_FINISHED"
        return [{**common, "type": rich_type, "stepName": step_name}]

    if event.type == event_types.TOOL_CALL:
        tool_name = str(event.payload.get("local_tool") or event.payload.get("mcp_tool") or "tool")
        tool_call_id = f"{event.id}:tool"
        return [
            {
                **common,
                "type": "TOOL_CALL_START",
                "toolCallId": tool_call_id,
                "toolCallName": tool_name,
            },
            {
                **common,
                "type": "TOOL_CALL_RESULT",
                "toolCallId": tool_call_id,
                "messageId": event.id,
                "content": event.payload,
            },
            {
                **common,
                "type": "TOOL_CALL_END",
                "toolCallId": tool_call_id,
            },
        ]

    if event.type == event_types.WORKFLOW_OUTPUT:
        message = event.payload.get("message")
        events: list[dict[str, Any]] = []
        if isinstance(message, str) and message:
            events.extend(
                [
                    {
                        **common,
                        "type": "TEXT_MESSAGE_START",
                        "messageId": event.id,
                        "role": "assistant",
                    },
                    {
                        **common,
                        "type": "TEXT_MESSAGE_CONTENT",
                        "messageId": event.id,
                        "delta": message,
                    },
                    {
                        **common,
                        "type": "TEXT_MESSAGE_END",
                        "messageId": event.id,
                    },
                ]
            )
        events.append({**common, "type": "RUN_FINISHED", "result": event.payload})
        return events

    if event.type == event_types.WORKFLOW_FAILED:
        message = event.payload.get("message") or "Workflow failed."
        return [
            {
                **common,
                "type": "RUN_ERROR",
                "message": str(message),
                "code": str(event.payload.get("code") or "workflow_failed"),
            }
        ]

    if event.type == event_types.CHECKPOINT_CREATED:
        return [
            {
                **common,
                **_custom_event(event, "checkpoint.created", event.payload),
            }
        ]

    if event.type in {event_types.HITL_REQUEST, event_types.HITL_RESPONSE}:
        return [
            {
                **common,
                **_custom_event(event, event.type, event.payload),
            }
        ]

    return [
        {
            **common,
            "type": "RAW",
        }
    ]


def rich_envelope_for_workflow_event(event: WorkflowEvent, sequence: int) -> dict[str, Any]:
    return {
        "type": "workflow.rich",
        "version": AGUI_VERSION,
        "id": f"{event.id}:rich:{sequence}",
        "thread_id": event.thread_id,
        "timestamp": event.timestamp,
        "source": "langgraph-order-resolution",
        "native_event": event.model_dump(),
        "events": rich_events_for_workflow_event(event),
    }


__all__ = [
    "AGUI_VERSION",
    "rich_envelope_for_workflow_event",
    "rich_events_for_workflow_event",
]
