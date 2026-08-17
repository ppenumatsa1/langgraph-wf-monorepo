from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.modules.underwriting import events as event_types

SAFE_EXPLANATION_PROTOCOL = "underwriting-safe-explanation/v1"
SAFE_RUN_STATUSES = frozenset({"IDLE", "IN_PROGRESS", "RUNNING", "COMPLETED", "CRASHED", "FAILED"})
SAFE_DECISIONS = frozenset(
    {
        "APPROVE",
        "APPROVED",
        "DECLINE",
        "DECLINED",
        "PENDING",
        "REFER",
        "REFERRED",
        "MANUAL_REVIEW",
    }
)
SAFE_EVENT_TYPES = frozenset(
    {
        event_types.WORKFLOW_START,
        event_types.WORKFLOW_COMPLETED,
        event_types.WORKFLOW_CRASHED,
        event_types.RESUME_REQUESTED,
        event_types.RESUME_COMPLETED,
        event_types.INIT_CONTEXT,
        event_types.RETRY_ATTEMPT,
        event_types.RETRY_BACKOFF,
        event_types.RETRY_EXHAUSTED,
        event_types.IDEMPOTENCY_SKIP,
        event_types.CHECK_COMPLETED,
        event_types.FAN_IN_RESULT_RECEIVED,
        event_types.FINAL_DECISION,
    }
)
SAFE_EXECUTOR_NAMES = frozenset(
    {
        "main",
        "init_context",
        "risk_score",
        "credit_check",
        "medical_check",
        "driving_check",
        "fan_in_aggregator",
        "final_decision",
    }
)
SAFE_INTENTS = frozenset({"summary", "status", "events", "checkpoints", "decision", "recovery"})
_RUN_ID_PATTERN = re.compile(r"run-[A-Za-z0-9_-]{1,60}\Z")


def is_safe_run_id(value: object) -> bool:
    return isinstance(value, str) and _RUN_ID_PATTERN.fullmatch(value) is not None


def normalize_status(value: object) -> str:
    normalized = str(value).upper()
    return normalized if normalized in SAFE_RUN_STATUSES else "UNKNOWN"


def normalize_decision(value: object) -> str | None:
    normalized = str(value).upper()
    return normalized if normalized in SAFE_DECISIONS else None


def normalize_timestamp(value: object) -> str | None:
    if isinstance(value, datetime):
        timestamp = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return timestamp.isoformat().replace("+00:00", "Z")
    if not isinstance(value, str):
        return None
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    timestamp = (
        timestamp.replace(tzinfo=UTC) if timestamp.tzinfo is None else timestamp.astimezone(UTC)
    )
    return timestamp.isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class SafeRunEvent:
    name: str
    timestamp: str | None
    executor: str

    def to_dict(self) -> dict[str, str | None]:
        return {"name": self.name, "timestamp": self.timestamp, "executor": self.executor}

    @classmethod
    def from_dict(cls, value: object) -> SafeRunEvent:
        if not isinstance(value, dict) or set(value) != {"name", "timestamp", "executor"}:
            raise ValueError("Invalid safe event")
        name = value.get("name")
        executor = value.get("executor")
        timestamp = value.get("timestamp")
        if name not in SAFE_EVENT_TYPES or executor not in SAFE_EXECUTOR_NAMES:
            raise ValueError("Invalid safe event")
        if timestamp is not None and normalize_timestamp(timestamp) is None:
            raise ValueError("Invalid safe event")
        return cls(name=name, timestamp=normalize_timestamp(timestamp), executor=executor)


@dataclass(frozen=True, slots=True)
class SafeSelectedRunContext:
    workflow_run_id: str
    status: str
    events: tuple[SafeRunEvent, ...]
    checkpoint_count: int
    latest_checkpoint_at: str | None
    final_decision: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_run_id": self.workflow_run_id,
            "status": self.status,
            "events": [event.to_dict() for event in self.events],
            "checkpoints": {
                "count": self.checkpoint_count,
                "latest_created_at": self.latest_checkpoint_at,
            },
            "output": {"final_decision": self.final_decision},
        }

    @classmethod
    def from_dict(cls, value: object) -> SafeSelectedRunContext:
        if not isinstance(value, dict) or set(value) != {
            "workflow_run_id",
            "status",
            "events",
            "checkpoints",
            "output",
        }:
            raise ValueError("Invalid safe selected run context")
        workflow_run_id = value.get("workflow_run_id")
        status = value.get("status")
        events = value.get("events")
        checkpoints = value.get("checkpoints")
        output = value.get("output")
        if (
            not is_safe_run_id(workflow_run_id)
            or status not in SAFE_RUN_STATUSES
            or not isinstance(events, list)
            or len(events) > 100
            or not isinstance(checkpoints, dict)
            or set(checkpoints) != {"count", "latest_created_at"}
            or not isinstance(output, dict)
            or set(output) != {"final_decision"}
        ):
            raise ValueError("Invalid safe selected run context")
        count = checkpoints.get("count")
        latest_checkpoint_at = checkpoints.get("latest_created_at")
        final_decision = output.get("final_decision")
        if (
            isinstance(count, bool)
            or not isinstance(count, int)
            or count < 0
            or (
                latest_checkpoint_at is not None
                and normalize_timestamp(latest_checkpoint_at) is None
            )
            or (final_decision is not None and final_decision not in SAFE_DECISIONS)
        ):
            raise ValueError("Invalid safe selected run context")
        return cls(
            workflow_run_id=workflow_run_id,
            status=status,
            events=tuple(SafeRunEvent.from_dict(event) for event in events),
            checkpoint_count=count,
            latest_checkpoint_at=normalize_timestamp(latest_checkpoint_at),
            final_decision=final_decision,
        )


@dataclass(frozen=True, slots=True)
class SafeRunExplanationRequest:
    workflow_run_id: str
    intent: str
    context: SafeSelectedRunContext

    def to_dict(self) -> dict[str, Any]:
        return {
            "protocol": SAFE_EXPLANATION_PROTOCOL,
            "workflow_run_id": self.workflow_run_id,
            "intent": self.intent,
            "context": self.context.to_dict(),
        }

    @classmethod
    def from_dict(cls, value: object) -> SafeRunExplanationRequest:
        if not isinstance(value, dict) or set(value) != {
            "protocol",
            "workflow_run_id",
            "intent",
            "context",
        }:
            raise ValueError("Invalid safe explanation request")
        workflow_run_id = value.get("workflow_run_id")
        intent = value.get("intent")
        context = SafeSelectedRunContext.from_dict(value.get("context"))
        if (
            value.get("protocol") != SAFE_EXPLANATION_PROTOCOL
            or not is_safe_run_id(workflow_run_id)
            or intent not in SAFE_INTENTS
            or context.workflow_run_id != workflow_run_id
        ):
            raise ValueError("Invalid safe explanation request")
        return cls(workflow_run_id=workflow_run_id, intent=intent, context=context)


def explanation_intent(messages: Iterable[object]) -> str:
    """Classify a question without forwarding or retaining its text."""
    last_user_message = ""
    for message in messages:
        if not isinstance(message, dict) or message.get("role") != "user":
            continue
        content = message.get("content")
        if isinstance(content, str):
            last_user_message = content[:1024].lower()
        elif isinstance(content, list):
            text_parts = [
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") == "text"
            ]
            last_user_message = " ".join(part for part in text_parts if isinstance(part, str))[
                :1024
            ].lower()
    if any(word in last_user_message for word in ("checkpoint", "resume", "recover")):
        return (
            "recovery"
            if "resume" in last_user_message or "recover" in last_user_message
            else "checkpoints"
        )
    if any(word in last_user_message for word in ("decision", "approve", "decline", "refer")):
        return "decision"
    if any(word in last_user_message for word in ("event", "stage", "timeline", "retry")):
        return "events"
    if any(
        word in last_user_message for word in ("status", "running", "complete", "crash", "fail")
    ):
        return "status"
    return "summary"


def selected_run_id_from_agui_context(value: object) -> str | None:
    if not isinstance(value, list):
        return None
    candidates: set[str] = set()
    for item in value:
        if not isinstance(item, dict) or not isinstance(item.get("value"), str):
            continue
        encoded_context = item["value"]
        if len(encoded_context) > 8192:
            continue
        try:
            context = json.loads(encoded_context)
        except json.JSONDecodeError:
            continue
        if not isinstance(context, dict):
            continue
        run_id = context.get("runId")
        if run_id is None:
            continue
        if not is_safe_run_id(run_id):
            raise ValueError("Invalid selected run")
        candidates.add(run_id)
    if len(candidates) > 1:
        raise ValueError("Conflicting selected runs")
    return next(iter(candidates), None)


def build_safe_explanation(context: SafeSelectedRunContext, intent: str) -> str:
    """Render only fields accepted by SafeSelectedRunContext."""
    status = f"Run {context.workflow_run_id} is {context.status}."
    checkpoints = f"Checkpoint count: {context.checkpoint_count}."
    if context.latest_checkpoint_at:
        checkpoints = f"{checkpoints} Latest checkpoint time: {context.latest_checkpoint_at}."
    decision = (
        f"Final decision: {context.final_decision}."
        if context.final_decision
        else "No allowlisted final decision is available."
    )
    events = (
        "Recent workflow events: "
        + ", ".join(f"{event.name} ({event.executor})" for event in context.events[-8:])
        + "."
        if context.events
        else "No allowlisted workflow events are available."
    )
    if intent == "status":
        return status
    if intent in {"checkpoints", "recovery"}:
        return f"{status} {checkpoints}"
    if intent == "decision":
        return f"{status} {decision}"
    if intent == "events":
        return f"{status} {events}"
    return f"{status} {events} {checkpoints} {decision}"
