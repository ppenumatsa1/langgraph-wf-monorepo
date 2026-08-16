from __future__ import annotations

import json
import logging
import os
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from app.api.v1.schemas.chat import ChatRunRequest
from app.api.v1.schemas.hitl import HitlResponseRequest
from app.core import telemetry as _telemetry
from app.core.telemetry import get_tracer
from app.modules.order_resolution.models import (
    ConcurrentStartError,
    PendingApprovalError,
)

logger = logging.getLogger(__name__)


def _apply_foundry_model_env_aliases() -> None:
    aliases = {
        "FOUNDRY_PROJECTS_ENDPOINT": "FOUNDRY_PROJECT_ENDPOINT",
        "FOUNDRY_MODEL_DEPLOYMENT_NAME": "AZURE_AI_MODEL_DEPLOYMENT_NAME",
    }
    for canonical_name, hosted_name in aliases.items():
        if os.getenv(canonical_name, "").strip():
            continue
        hosted_value = os.getenv(hosted_name, "").strip()
        if hosted_value:
            os.environ[canonical_name] = hosted_value


def _database_url_host(value: str) -> str:
    if not value:
        return ""
    match = re.match(r"^[a-zA-Z0-9+.-]+://(?:[^@/]+@)?([^:/?]+)", value)
    return match.group(1).strip().lower() if match else ""


def _apply_runtime_database_url_override() -> None:
    runtime_database_url = os.getenv("FOUNDRY_RUNTIME_DATABASE_URL", "").strip()
    if not runtime_database_url:
        runtime_database_url = os.getenv("RUNTIME_DATABASE_URL", "").strip()
    if not runtime_database_url:
        return
    database_url = os.getenv("DATABASE_URL", "").strip()
    database_host = _database_url_host(database_url)
    if not database_url or database_host in {"localhost", "127.0.0.1"}:
        os.environ["DATABASE_URL"] = runtime_database_url


def _apply_appinsights_connection_env_aliases() -> None:
    canonical = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip()
    if canonical and not canonical.startswith("${"):
        return

    appinsights_alias = os.getenv("APPINSIGHTS_CONNECTION_STRING", "").strip()
    if not appinsights_alias or appinsights_alias.startswith("${"):
        return

    # AgentServer's bootstrap parser is strict; provide a compact canonical form.
    match = re.search(r"InstrumentationKey=([^;\s]+)", appinsights_alias)
    if match:
        os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"] = f"InstrumentationKey={match.group(1)}"
        return

    os.environ["APPLICATIONINSIGHTS_CONNECTION_STRING"] = appinsights_alias


_apply_foundry_model_env_aliases()
_apply_runtime_database_url_override()
_apply_appinsights_connection_env_aliases()

if os.getenv("FOUNDRY_HOSTED_SKIP_APP_INIT_FOR_TESTS", "").strip().lower() == "true":
    order_resolution_service = None
    workflow_run_repository = None
else:
    from app.core.container import order_resolution_service, workflow_run_repository


@dataclass(frozen=True)
class _ParsedInput:
    conversation_id: str
    message: str | None
    decision: str | None
    checkpoint_id: str | None


def _parse_debug_enabled() -> bool:
    return os.getenv("FOUNDRY_DEBUG_PARSE_INPUT", "").strip().lower() in {"1", "true", "yes", "on"}


def _emit_parse_debug(payload: dict[str, Any], context: Any | None, parsed: _ParsedInput) -> None:
    if not _parse_debug_enabled():
        return

    payload_input = payload.get("input")
    payload_summary: dict[str, Any] = {
        "parsed_conversation_id": parsed.conversation_id,
        "parsed_decision": parsed.decision,
        "parsed_checkpoint_id": parsed.checkpoint_id,
        "parsed_message_preview": (parsed.message or "")[:120],
        "payload_keys": sorted(payload.keys()),
        "input_type": type(payload_input).__name__,
        "has_conversation": isinstance(payload.get("conversation"), dict),
    }
    if isinstance(payload_input, list) and payload_input:
        first_item = payload_input[0]
        payload_summary["input_first_type"] = type(first_item).__name__
        if isinstance(first_item, dict):
            payload_summary["input_first_keys"] = sorted(first_item.keys())

    if context is not None:
        context_attrs = [
            name
            for name in ("id", "session_id", "conversation_id", "request_body")
            if hasattr(context, name)
        ]
        payload_summary["context_attrs"] = context_attrs
        context_request_body = getattr(context, "request_body", None)
        if isinstance(context_request_body, dict):
            payload_summary["context_request_body_keys"] = sorted(context_request_body.keys())

    print(f"FOUNDRY_PARSE_DEBUG {json.dumps(payload_summary, default=str)}", flush=True)


def _load_responses_types() -> tuple[type[Any], type[Any], type[Any], type[Any], type[Any]]:
    from azure.ai.agentserver.responses import (  # type: ignore[import-not-found]
        CreateResponse,
        InMemoryResponseProvider,
        ResponseContext,
        ResponsesAgentServerHost,
        TextResponse,
    )

    return (
        ResponsesAgentServerHost,
        CreateResponse,
        ResponseContext,
        TextResponse,
        InMemoryResponseProvider,
    )


def _coerce_payload(create_response: Any) -> dict[str, Any]:
    if isinstance(create_response, dict):
        return dict(create_response)
    if hasattr(create_response, "model_dump"):
        return create_response.model_dump()
    if hasattr(create_response, "dict"):
        return create_response.dict()
    return {}


def _nested_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        if "value" in value:
            return _nested_text(value["value"])
        if "text" in value:
            return _nested_text(value["text"])
        if "input_text" in value:
            return _nested_text(value["input_text"])
        if "content" in value:
            return _nested_text(value["content"])
        if "input" in value:
            return _nested_text(value["input"])
        if "message" in value:
            return _nested_text(value["message"])
        if "output" in value:
            return _nested_text(value["output"])
        return ""
    if isinstance(value, list):
        parts = [_nested_text(item) for item in value]
        return " ".join(part for part in parts if part).strip()
    return str(value).strip()


def _coerce_conversation_id(payload: dict[str, Any], context: Any | None) -> str:
    payload_conversation = payload.get("conversation")
    if isinstance(payload_conversation, str) and payload_conversation.strip():
        return payload_conversation.strip()
    if isinstance(payload_conversation, dict):
        payload_conversation_id = payload_conversation.get("id")
        if isinstance(payload_conversation_id, str) and payload_conversation_id.strip():
            return payload_conversation_id.strip()

    previous_response_id = payload.get("previous_response_id")
    if isinstance(previous_response_id, str) and previous_response_id.strip():
        return previous_response_id.strip()

    if context is not None:
        for key in ("conversation_id", "conversation", "previous_response_id"):
            value = getattr(context, key, None)
            if isinstance(value, str) and value.strip():
                return value.strip()
            if isinstance(value, dict):
                conversation_id = value.get("id")
                if isinstance(conversation_id, str) and conversation_id.strip():
                    return conversation_id.strip()

        for key in ("request", "request_body", "body", "payload", "raw_request"):
            nested = getattr(context, key, None)
            if hasattr(nested, "model_dump"):
                nested = nested.model_dump()
            elif hasattr(nested, "dict"):
                nested = nested.dict()
            if isinstance(nested, dict):
                nested_conversation = nested.get("conversation")
                if isinstance(nested_conversation, str) and nested_conversation.strip():
                    return nested_conversation.strip()
                if isinstance(nested_conversation, dict):
                    nested_conversation_id = nested_conversation.get("id")
                    if isinstance(nested_conversation_id, str) and nested_conversation_id.strip():
                        return nested_conversation_id.strip()
                nested_previous_response_id = nested.get("previous_response_id")
                if (
                    isinstance(nested_previous_response_id, str)
                    and nested_previous_response_id.strip()
                ):
                    return nested_previous_response_id.strip()

    payload_id = payload.get("id")
    if isinstance(payload_id, str) and payload_id.strip():
        return payload_id.strip()
    return str(uuid4())


def _iter_input_items(payload: dict[str, Any]) -> Iterable[dict[str, Any]]:
    raw_input = payload.get("input")
    if isinstance(raw_input, dict):
        return [raw_input]
    if isinstance(raw_input, list):
        return [item for item in raw_input if isinstance(item, dict)]
    return []


def _parse_function_call_output(items: Iterable[dict[str, Any]]) -> tuple[str | None, str | None]:
    checkpoint_id: str | None = None
    decision: str | None = None
    for item in items:
        if str(item.get("type", "")).strip().lower() != "function_call_output":
            continue
        call_id = item.get("call_id")
        if isinstance(call_id, str) and call_id.strip():
            checkpoint_id = call_id.strip()
        output = item.get("output")
        if isinstance(output, dict):
            out_checkpoint = output.get("checkpoint_id")
            out_decision = output.get("decision")
            if isinstance(out_checkpoint, str) and out_checkpoint.strip():
                checkpoint_id = out_checkpoint.strip()
            if isinstance(out_decision, str):
                lowered = out_decision.strip().lower()
                if lowered in {"approve", "reject"}:
                    decision = lowered
        elif isinstance(output, str):
            normalized_output = output.strip()
            try:
                decoded = json.loads(normalized_output)
            except (TypeError, ValueError):
                decoded = None
            if isinstance(decoded, dict):
                out_checkpoint = decoded.get("checkpoint_id")
                out_decision = decoded.get("decision")
                if isinstance(out_checkpoint, str) and out_checkpoint.strip():
                    checkpoint_id = out_checkpoint.strip()
                if isinstance(out_decision, str):
                    lowered_decision = out_decision.strip().lower()
                    if lowered_decision in {"approve", "reject"}:
                        decision = lowered_decision
            lowered = normalized_output.lower()
            if lowered in {"approve", "reject"}:
                decision = lowered
    return checkpoint_id, decision


def _message_from_context(context: Any | None) -> str | None:
    if context is None:
        return None
    direct_fields = (
        "input",
        "message",
        "user_message",
        "prompt",
        "text",
        "query",
    )
    nested_fields = (
        "request",
        "request_body",
        "body",
        "payload",
        "raw_request",
    )
    for field in direct_fields:
        text = _nested_text(getattr(context, field, None))
        if text:
            return text
    for field in nested_fields:
        raw_value = getattr(context, field, None)
        if hasattr(raw_value, "model_dump"):
            raw_value = raw_value.model_dump()
        elif hasattr(raw_value, "dict"):
            raw_value = raw_value.dict()
        text = _nested_text(raw_value)
        if text:
            return text
    return None


def _resume_from_context_headers(context: Any | None) -> tuple[str | None, str | None]:
    if context is None:
        return None, None
    raw_headers = getattr(context, "client_headers", None)
    if not isinstance(raw_headers, dict):
        return None, None
    headers = {
        str(key).strip().lower(): value
        for key, value in raw_headers.items()
        if isinstance(value, str)
    }
    checkpoint_id = headers.get("x-client-checkpoint-id")
    checkpoint_id = checkpoint_id.strip() if checkpoint_id and checkpoint_id.strip() else None
    raw_decision = headers.get("x-client-decision")
    decision = raw_decision.strip().lower() if raw_decision else None
    if decision not in {"approve", "reject"}:
        decision = None
    return checkpoint_id, decision


def _decision_from_text(
    message: str | None,
    *,
    has_pending_approval: bool,
) -> str | None:
    if not message or not has_pending_approval:
        return None
    normalized = " ".join(message.strip().lower().split())
    if re.fullmatch(r"(?:approve|approved|yes)(?:[.!])?", normalized):
        return "approve"
    if re.fullmatch(r"(?:reject|rejected|no)(?:[.!])?", normalized):
        return "reject"
    return None


def _pending_checkpoint_id(thread_id: str) -> str | None:
    if workflow_run_repository is None:
        return None
    details = workflow_run_repository.get_workflow_run(thread_id)
    if not details:
        return None
    for approval in details.pending_approvals:
        if approval.status == "pending":
            return approval.checkpoint_id
    return None


def _parse_input(create_response: Any, context: Any | None) -> _ParsedInput:
    payload = _coerce_payload(create_response)
    conversation_id = _coerce_conversation_id(payload, context)
    metadata = payload.get("metadata")
    message = _nested_text(payload.get("message")) or _nested_text(payload.get("input"))
    message = message or _message_from_context(context)
    checkpoint_id: str | None = None
    decision: str | None = None
    explicit_checkpoint = payload.get("checkpoint_id")
    if isinstance(explicit_checkpoint, str) and explicit_checkpoint.strip():
        checkpoint_id = explicit_checkpoint.strip()
    explicit_decision = payload.get("decision")
    if isinstance(explicit_decision, str):
        lowered = explicit_decision.strip().lower()
        if lowered in {"approve", "reject"}:
            decision = lowered
    if isinstance(metadata, dict):
        maybe_checkpoint = metadata.get("checkpoint_id")
        if isinstance(maybe_checkpoint, str) and maybe_checkpoint.strip():
            checkpoint_id = maybe_checkpoint.strip()
        maybe_decision = metadata.get("decision")
        if isinstance(maybe_decision, str):
            lowered = maybe_decision.strip().lower()
            if lowered in {"approve", "reject"}:
                decision = lowered
    header_checkpoint, header_decision = _resume_from_context_headers(context)
    if header_checkpoint:
        checkpoint_id = header_checkpoint
    if header_decision:
        decision = header_decision
    input_checkpoint, input_decision = _parse_function_call_output(_iter_input_items(payload))
    if input_checkpoint:
        checkpoint_id = input_checkpoint
    if input_decision:
        decision = input_decision
    if decision is None:
        decision = _decision_from_text(
            message,
            has_pending_approval=(_pending_checkpoint_id(conversation_id) is not None),
        )
    parsed = _ParsedInput(
        conversation_id=conversation_id,
        message=message or None,
        decision=decision,
        checkpoint_id=checkpoint_id,
    )
    _emit_parse_debug(payload, context, parsed)
    return parsed


def _serialize_workflow(thread_id: str) -> dict[str, Any]:
    details = workflow_run_repository.get_workflow_run(thread_id)
    if details is None:
        return {
            "thread_id": thread_id,
            "status": "failed",
            "events": [],
            "pending_approvals": [],
            "latest_output": None,
            "message": "Workflow run not found.",
        }
    message = (
        str(details.latest_output.get("message"))
        if isinstance(details.latest_output, dict) and details.latest_output.get("message")
        else ""
    )
    if not message and any(approval.status == "pending" for approval in details.pending_approvals):
        message = "Approval is required before this order resolution can continue."
    return {
        "thread_id": details.thread_id,
        "status": details.status,
        "events": [event.model_dump() for event in details.events],
        "pending_approvals": [approval.model_dump() for approval in details.pending_approvals],
        "latest_output": details.latest_output,
        "message": message,
    }


def _set_span_attribute(span: Any, key: str, value: Any) -> None:
    if value is None:
        return
    if isinstance(value, str | bool | int | float):
        span.set_attribute(key, value)


def _trace_evaluation_content_enabled() -> bool:
    value = os.getenv(
        "TRACE_EVALUATION_RECORD_CONTENT",
        os.getenv("FOUNDRY_TRACE_EVALUATION_RECORD_CONTENT", "false"),
    )
    return value.strip().lower() in {
        "1",
        "true",
        "yes",
    }


def _set_trace_evaluation_input(span: Any, parsed: _ParsedInput) -> None:
    if not _trace_evaluation_content_enabled():
        return
    input_text = parsed.message or parsed.decision
    if not input_text:
        return
    span.set_attribute(
        "gen_ai.input.messages",
        json.dumps(
            [
                {
                    "role": "user",
                    "parts": [{"type": "text", "content": input_text}],
                }
            ]
        ),
    )


def _set_trace_evaluation_output(span: Any, payload: dict[str, Any]) -> None:
    if not _trace_evaluation_content_enabled():
        return
    message = payload.get("message")
    if not isinstance(message, str) or not message:
        return
    span.set_attribute(
        "gen_ai.output.messages",
        json.dumps(
            [
                {
                    "role": "assistant",
                    "parts": [{"type": "text", "content": message}],
                    "finish_reason": "stop",
                }
            ]
        ),
    )


async def _run_from_responses(
    create_response: Any, context: Any | None, text_response: type[Any]
) -> Any:
    startup = getattr(order_resolution_service, "startup", None)
    if callable(startup):
        await startup()
    parsed = _parse_input(create_response, context)
    tracer = get_tracer("foundry.responses")
    # Anchor all turn-level telemetry under a single invocation span.
    with tracer.start_as_current_span("foundry.responses.invoke") as span:
        _set_span_attribute(span, "workflow.thread_id", parsed.conversation_id)
        _set_span_attribute(span, "workflow.session_id", parsed.conversation_id)
        _set_span_attribute(span, "foundry.protocol", "responses")
        _set_span_attribute(span, "gen_ai.operation.name", "invoke_agent")
        _set_span_attribute(
            span,
            "gen_ai.agent.name",
            os.getenv("FOUNDRY_HOSTED_AGENT_NAME", "order-resolution-hosted"),
        )
        _set_span_attribute(
            span,
            "gen_ai.agent.id",
            os.getenv("FOUNDRY_HOSTED_AGENT_ID", "order-resolution-hosted"),
        )
        _set_span_attribute(span, "gen_ai.conversation.id", parsed.conversation_id)
        _set_trace_evaluation_input(span, parsed)
        checkpoint_id_for_span: str | None = None
        try:
            if parsed.decision:
                checkpoint_id = parsed.checkpoint_id or _pending_checkpoint_id(
                    parsed.conversation_id
                )
                checkpoint_id_for_span = checkpoint_id
                if checkpoint_id is None:
                    payload = {
                        "thread_id": parsed.conversation_id,
                        "status": "failed",
                        "events": [],
                        "pending_approvals": [],
                        "message": "No pending approval found for this conversation.",
                    }
                else:
                    hitl_result = await order_resolution_service.respond_hitl(
                        HitlResponseRequest(
                            checkpoint_id=checkpoint_id,
                            decision=parsed.decision,
                            reviewer="foundry-conversation",
                            comments="decision received from responses conversation",
                        )
                    )
                    resumed_thread_id = getattr(hitl_result, "thread_id", parsed.conversation_id)
                    payload = _serialize_workflow(resumed_thread_id)
            elif parsed.message:
                try:
                    await order_resolution_service.start_chat_run(
                        ChatRunRequest(
                            message=parsed.message,
                            thread_id=parsed.conversation_id,
                            session_id=parsed.conversation_id,
                            customer_id="foundry-hosted",
                        )
                    )
                    payload = _serialize_workflow(parsed.conversation_id)
                except PendingApprovalError:
                    payload = _serialize_workflow(parsed.conversation_id)
                    payload["message"] = (
                        "Resolve the pending approval before sending a new message."
                    )
                except ConcurrentStartError as exc:
                    payload = _serialize_workflow(parsed.conversation_id)
                    payload["message"] = str(exc)
            else:
                payload = {
                    "thread_id": parsed.conversation_id,
                    "status": "failed",
                    "events": [],
                    "pending_approvals": [],
                    "message": "message or input is required",
                }
            _set_span_attribute(span, "workflow.checkpoint_id", checkpoint_id_for_span)
            _set_span_attribute(span, "workflow.status", payload.get("status"))
            events = payload.get("events")
            if isinstance(events, list):
                _set_span_attribute(span, "workflow.event_count", len(events))
            _set_trace_evaluation_output(span, payload)
            response_text = json.dumps(payload)
            return text_response(context, create_response, text=response_text)
        except Exception as exc:
            span.record_exception(exc)
            raise


def _build_app() -> Any:
    ResponsesAgentServerHost, _, _, TextResponse, _ = _load_responses_types()
    host = ResponsesAgentServerHost()

    async def handler(
        create_response: Any,
        context: Any | None = None,
        cancellation_signal: Any | None = None,
    ) -> Any:
        return await _run_from_responses(create_response, context, TextResponse)

    host.response_handler(handler)
    return host


def _initialize_app() -> Any:
    def _env_state(name: str) -> dict[str, Any]:
        value = os.getenv(name, "")
        segments = [segment for segment in value.split(";") if segment]
        kv_segments = [segment for segment in segments if "=" in segment]
        return {
            "present": bool(value),
            "placeholder": value.startswith("${"),
            "has_instrumentation_key": "InstrumentationKey=" in value,
            "length": len(value),
            "semicolon_count": value.count(";"),
            "equals_count": value.count("="),
            "segment_count": len(segments),
            "kv_segment_count": len(kv_segments),
        }

    # AgentServerHost configures the hosted OTel provider before LangGraph
    # callback tracing attaches to it.
    hosted_app = _build_app()
    auto_tracing_enabled = _telemetry.enable_langgraph_auto_tracing()
    logger.info(
        "Hosted LangGraph auto-tracing initialized: enabled=%s",
        auto_tracing_enabled,
    )
    logger.info(
        "Hosted env diagnostic: appinsights=%s appinsights_alias=%s database_url=%s runtime_database_url=%s",
        _env_state("APPLICATIONINSIGHTS_CONNECTION_STRING"),
        _env_state("APPINSIGHTS_CONNECTION_STRING"),
        _env_state("DATABASE_URL"),
        _env_state("FOUNDRY_RUNTIME_DATABASE_URL"),
    )
    print(
        "HOSTED_ENV_DIAGNOSTIC "
        + json.dumps(
            {
                "applicationinsights_connection_string": _env_state(
                    "APPLICATIONINSIGHTS_CONNECTION_STRING"
                ),
                "appinsights_connection_string": _env_state("APPINSIGHTS_CONNECTION_STRING"),
                "database_url": _env_state("DATABASE_URL"),
                "foundry_runtime_database_url": _env_state("FOUNDRY_RUNTIME_DATABASE_URL"),
            },
            separators=(",", ":"),
        ),
        file=sys.stderr,
        flush=True,
    )
    return hosted_app


app = None if os.getenv("FOUNDRY_HOSTED_SKIP_APP_INIT_FOR_TESTS") == "true" else _initialize_app()


if __name__ == "__main__":
    (_initialize_app() if app is None else app).run()
