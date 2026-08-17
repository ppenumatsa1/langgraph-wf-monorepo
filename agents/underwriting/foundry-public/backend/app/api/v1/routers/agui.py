from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.core.container import get_underwriting_service
from app.core.telemetry import annotate_current_span
from app.modules.underwriting.models import UnderwritingApplication
from app.modules.underwriting.service import UnderwritingService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/underwriting", tags=["underwriting"])
service: UnderwritingService | None = None


def _service() -> UnderwritingService:
    return service or get_underwriting_service()


def _parse_request(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=422, detail="Invalid AG-UI request")
    messages = payload.get("messages")
    if not isinstance(messages, list):
        raise HTTPException(status_code=422, detail="AG-UI request requires messages")
    for message in reversed(messages):
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content")
        if not isinstance(content, str):
            continue
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise HTTPException(
                status_code=422, detail="AG-UI request message must contain JSON"
            ) from exc
        if not isinstance(parsed, dict):
            raise HTTPException(status_code=422, detail="AG-UI request payload must be an object")
        workflow_run_id = parsed.get("workflow_run_id")
        if not isinstance(workflow_run_id, str) or not workflow_run_id.startswith("run-"):
            raise HTTPException(
                status_code=422,
                detail="AG-UI request requires a workflow_run_id beginning with 'run-'",
            )
        return parsed
    raise HTTPException(status_code=422, detail="AG-UI request requires a user message")


def _sse_event(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event, separators=(',', ':'))}\n\n"


async def _emit_new_events(
    *,
    workflow_run_id: str,
    emitted_event_ids: set[int],
) -> list[str]:
    frames: list[str] = []
    for event in _service().get_events(workflow_run_id):
        event_id = event.get("id")
        if not isinstance(event_id, int) or event_id in emitted_event_ids:
            continue
        emitted_event_ids.add(event_id)
        frames.append(
            _sse_event(
                {
                    "type": "CUSTOM",
                    "name": "underwriting.event",
                    "value": {
                        "workflowRunId": workflow_run_id,
                        "eventType": str(event.get("event_type", "event")),
                        "executorName": str(event.get("executor_name", "workflow")),
                        "createdAt": str(event.get("created_at", "")),
                    },
                }
            )
        )
    return frames


async def _stream_run(request_payload: dict[str, Any]) -> AsyncGenerator[str, None]:
    workflow_run_id = str(request_payload["workflow_run_id"])
    action = str(request_payload.get("action", "start"))
    annotate_current_span(workflow_run_id, action)
    thread_id = f"underwriting-ui-{uuid4().hex}"
    run_id = f"underwriting-stream-{uuid4().hex}"
    yield _sse_event({"type": "RUN_STARTED", "threadId": thread_id, "runId": run_id})

    if action == "resume":
        task = asyncio.create_task(_service().resume_run(workflow_run_id))
    else:
        application = request_payload.get("application")
        if not isinstance(application, dict):
            raise HTTPException(status_code=422, detail="AG-UI start requires an application")
        task = asyncio.create_task(
            _service().start_run(
                workflow_run_id=workflow_run_id,
                application=UnderwritingApplication(**application),
                fail_risk_once=bool(request_payload.get("fail_risk_once", False)),
                fail_credit_randomly=bool(request_payload.get("fail_credit_randomly", False)),
                crash_after_executor=(
                    str(request_payload["crash_after_executor"])
                    if request_payload.get("crash_after_executor") is not None
                    else None
                ),
            )
        )

    emitted_event_ids: set[int] = set()
    error_message: str | None = None
    while not task.done():
        for frame in await _emit_new_events(
            workflow_run_id=workflow_run_id,
            emitted_event_ids=emitted_event_ids,
        ):
            yield frame
        await asyncio.sleep(0.1)

    try:
        await task
    except Exception as exc:
        error_message = str(exc)
        logger.exception("agui run failed workflow_run_id=%s action=%s", workflow_run_id, action)

    for frame in await _emit_new_events(
        workflow_run_id=workflow_run_id,
        emitted_event_ids=emitted_event_ids,
    ):
        yield frame

    if error_message is not None:
        yield _sse_event(
            {
                "type": "RUN_FINISHED",
                "threadId": thread_id,
                "runId": run_id,
                "outcome": {"type": "error", "message": error_message},
            }
        )
        return

    yield _sse_event(
        {
            "type": "RUN_FINISHED",
            "threadId": thread_id,
            "runId": run_id,
            "outcome": {"type": "success"},
        }
    )


@router.post("/ag-ui")
async def agui_run(request: Request) -> StreamingResponse:
    try:
        payload = await request.json()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="Invalid AG-UI JSON") from exc
    request_payload = _parse_request(payload)
    return StreamingResponse(
        _stream_run(request_payload),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
