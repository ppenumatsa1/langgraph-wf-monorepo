from __future__ import annotations

from typing import Annotated

from app.api.v1.schemas.sessions import SessionMessageListResponse
from app.api.v1.schemas.workflows import CursorPagination
from app.core.container import workflow_run_repository
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.get("/{session_id}/messages", response_model=SessionMessageListResponse)
async def list_session_messages(
    session_id: str,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[int | None, Query(ge=1)] = None,
) -> SessionMessageListResponse:
    items, next_cursor, has_more = workflow_run_repository.list_session_messages(
        session_id=session_id,
        limit=limit,
        cursor=cursor,
    )
    return SessionMessageListResponse(
        items=items,
        pagination=CursorPagination(
            limit=limit,
            next_cursor=next_cursor,
            has_more=has_more,
        ),
    )
