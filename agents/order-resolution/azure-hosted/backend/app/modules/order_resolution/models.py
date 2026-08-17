from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PendingApprovalError(RuntimeError):
    def __init__(self, thread_id: str, checkpoint_id: str) -> None:
        self.thread_id = thread_id
        self.checkpoint_id = checkpoint_id
        super().__init__(f"Thread {thread_id} is waiting for approval checkpoint {checkpoint_id}.")


class ConcurrentStartError(RuntimeError):
    def __init__(self, thread_id: str) -> None:
        self.thread_id = thread_id
        super().__init__(f"Thread {thread_id} already has an active workflow invocation.")


class WorkflowEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    type: str
    thread_id: str
    timestamp: str = Field(default_factory=utc_now_iso)
    payload: dict[str, Any] = Field(default_factory=dict)


@dataclass
class WorkflowContext:
    run_id: str
    thread_id: str
    session_id: str
    customer_id: str
    user_message: str
