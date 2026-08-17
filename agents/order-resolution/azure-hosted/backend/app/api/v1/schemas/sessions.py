from __future__ import annotations

from app.api.v1.schemas.workflows import CursorPagination
from pydantic import BaseModel


class SessionMessage(BaseModel):
    id: int
    session_id: str
    thread_id: str
    role: str
    content: str
    created_at: str


class SessionMessageListResponse(BaseModel):
    items: list[SessionMessage]
    pagination: CursorPagination
