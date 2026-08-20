from __future__ import annotations

from typing import Any, Literal

from app.modules.order_resolution.models import WorkflowEvent
from pydantic import BaseModel

WorkflowRunStatus = Literal["running", "waiting_approval", "completed", "failed", "escalated"]


class WorkflowRunListItem(BaseModel):
    thread_id: str
    status: WorkflowRunStatus
    input_summary: str
    created_at: str
    updated_at: str


class WorkflowRunListResponse(BaseModel):
    items: list[WorkflowRunListItem]
    page: int
    page_size: int
    total: int


class CursorPagination(BaseModel):
    limit: int
    next_cursor: str | None = None
    has_more: bool = False


class WorkflowRunMetadata(BaseModel):
    thread_id: str
    status: WorkflowRunStatus
    started_at: str | None = None
    completed_at: str | None = None
    duration_ms: int | None = None
    current_stage: str | None = None


class PendingApproval(BaseModel):
    approval_id: str
    checkpoint_id: str
    action: str | None = None
    order_id: str | None = None
    amount: float | int | None = None
    question: str | None = None
    reviewer: str | None = None
    comments: str | None = None
    status: Literal["pending", "approved", "rejected"] = "pending"
    requested_at: str
    resolved_at: str | None = None


class WorkflowRunDetailsResponse(BaseModel):
    thread_id: str
    status: WorkflowRunStatus
    input: str
    events: list[WorkflowEvent]
    pending_approvals: list[PendingApproval]
    latest_output: dict[str, Any] | None = None
    metadata: WorkflowRunMetadata


class WorkflowEventListResponse(BaseModel):
    items: list[WorkflowEvent]
    pagination: CursorPagination
