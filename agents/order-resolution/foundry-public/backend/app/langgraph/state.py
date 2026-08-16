from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict


class OrderResolutionState(TypedDict, total=False):
    run_id: str
    thread_id: str
    session_id: str
    customer_id: str
    user_message: str
    conversation_history: list[dict[str, Any]]
    trace_context: dict[str, str] | None
    request_kind: Literal["explanation", "resolution"]
    triage_summary: str
    triage_mode: dict[str, str]
    issue_type: str
    order: dict[str, Any]
    policy: str
    rag_result: dict[str, Any]
    mcp_result: dict[str, Any]
    action: str
    amount: float
    requires_approval: bool
    approval_checkpoint_id: str
    approval_decision: Literal["approve", "reject"]
    reviewer: str
    comments: str | None
    submission_id: str
    output: dict[str, Any]
    terminal_status: Literal["completed", "escalated", "failed"]
    events: Annotated[list[dict[str, Any]], operator.add]
