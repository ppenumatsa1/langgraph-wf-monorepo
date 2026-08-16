from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ChatRunRequest(BaseModel):
    message: str = Field(min_length=1)
    thread_id: str | None = None
    session_id: str | None = None
    customer_id: str = Field(default="cust-demo")
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=255)


class ChatRunResponse(BaseModel):
    run_id: str
    thread_id: str
    status: Literal["accepted"] = "accepted"
