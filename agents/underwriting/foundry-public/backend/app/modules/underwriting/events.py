from __future__ import annotations

WORKFLOW_START = "workflow_start"
WORKFLOW_COMPLETED = "workflow_completed"
WORKFLOW_CRASHED = "workflow_crashed"
RESUME_REQUESTED = "resume_requested"
RESUME_COMPLETED = "resume_completed"
INIT_CONTEXT = "init_context"
RETRY_ATTEMPT = "retry_attempt"
RETRY_BACKOFF = "retry_backoff"
RETRY_EXHAUSTED = "retry_exhausted"
IDEMPOTENCY_SKIP = "idempotency_skip"
CHECK_COMPLETED = "check_completed"
FAN_IN_RESULT_RECEIVED = "fan_in_result_received"
FINAL_DECISION = "final_decision"

__all__ = [
    "CHECK_COMPLETED",
    "FAN_IN_RESULT_RECEIVED",
    "FINAL_DECISION",
    "IDEMPOTENCY_SKIP",
    "INIT_CONTEXT",
    "RESUME_COMPLETED",
    "RESUME_REQUESTED",
    "RETRY_ATTEMPT",
    "RETRY_BACKOFF",
    "RETRY_EXHAUSTED",
    "WORKFLOW_COMPLETED",
    "WORKFLOW_CRASHED",
    "WORKFLOW_START",
]
