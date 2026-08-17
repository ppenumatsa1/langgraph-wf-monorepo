from __future__ import annotations

import json
import re
from collections.abc import AsyncGenerator
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.core.config import load_settings
from app.core.container import get_copilot_bridge
from app.modules.underwriting.copilot import (
    explanation_intent,
    selected_run_id_from_agui_context,
)
from app.modules.underwriting.copilot_bridge import UnderwritingCopilotBridge

router = APIRouter(prefix="/api/v1/underwriting", tags=["underwriting"])
bridge: UnderwritingCopilotBridge | Any | None = None
_AGUI_ID_PATTERN = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
_COPILOT_AGENT_ID = "underwriting-run-assistant"


def _bridge() -> Any:
    return bridge or get_copilot_bridge()


def _require_configured_frontend_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin != load_settings().frontend_origin:
        raise HTTPException(status_code=403, detail="A configured frontend origin is required")


def _agui_id(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or _AGUI_ID_PATTERN.fullmatch(value) is None:
        raise HTTPException(status_code=422, detail=f"Invalid AG-UI {key}")
    return value


def _parse_request(payload: object) -> tuple[str, str, str | None, str]:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Invalid AG-UI request")
    thread_id = _agui_id(payload, "threadId")
    run_id = _agui_id(payload, "runId")
    messages = payload.get("messages")
    if not isinstance(messages, list) or len(messages) > 100:
        raise HTTPException(status_code=422, detail="Invalid AG-UI messages")
    try:
        selected_run_id = selected_run_id_from_agui_context(payload.get("context"))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid selected run context") from exc
    return thread_id, run_id, selected_run_id, explanation_intent(messages)


def _sse_event(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, separators=(',', ':'))}\n\n"


async def _agui_stream(
    *,
    thread_id: str,
    run_id: str,
    explanation: str,
) -> AsyncGenerator[str, None]:
    message_id = f"assistant-{uuid4().hex}"
    yield _sse_event({"type": "RUN_STARTED", "threadId": thread_id, "runId": run_id})
    yield _sse_event(
        {
            "type": "TEXT_MESSAGE_START",
            "messageId": message_id,
            "role": "assistant",
        }
    )
    yield _sse_event(
        {
            "type": "TEXT_MESSAGE_CONTENT",
            "messageId": message_id,
            "delta": explanation,
        }
    )
    yield _sse_event({"type": "TEXT_MESSAGE_END", "messageId": message_id})
    yield _sse_event(
        {
            "type": "RUN_FINISHED",
            "threadId": thread_id,
            "runId": run_id,
            "outcome": {"type": "success"},
        }
    )


@router.get("/copilotkit/info")
async def copilotkit_info() -> dict[str, object]:
    return {
        "version": "1.0",
        "mode": "sse",
        "audioFileTranscriptionEnabled": False,
        "threadEndpoints": {
            "list": False,
            "inspect": False,
            "mutations": False,
            "realtimeMetadata": False,
        },
        "agents": {
            _COPILOT_AGENT_ID: {
                "name": "Underwriting Run Assistant",
                "className": "UnderwritingRunAssistant",
                "description": "Explains the allowlisted status and execution history of an underwriting run.",
            }
        },
    }


@router.post("/copilotkit/agent/{agent_id}/run")
async def copilotkit_run(agent_id: str, request: Request) -> StreamingResponse:
    if agent_id != _COPILOT_AGENT_ID:
        raise HTTPException(status_code=404, detail="CopilotKit agent was not found")
    _require_configured_frontend_origin(request)
    try:
        payload = await request.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="Invalid AG-UI JSON") from exc
    thread_id, run_id, selected_run_id, intent = _parse_request(payload)
    try:
        explanation = await _bridge().explain(selected_run_id, intent)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Hosted assistant is unavailable") from exc
    return StreamingResponse(
        _agui_stream(thread_id=thread_id, run_id=run_id, explanation=explanation),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
