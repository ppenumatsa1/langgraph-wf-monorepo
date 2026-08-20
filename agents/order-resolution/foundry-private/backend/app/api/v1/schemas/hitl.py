from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HitlResponseRequest(BaseModel):
    checkpoint_id: str
    decision: Literal["approve", "reject"]
    reviewer: str = Field(default="human-reviewer")
    comments: str | None = None


class HitlResponseResult(BaseModel):
    accepted: bool
    checkpoint_id: str
    thread_id: str
