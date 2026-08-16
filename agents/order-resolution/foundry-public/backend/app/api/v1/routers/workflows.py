from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from app.api.v1.schemas.workflows import (
    CursorPagination,
    WorkflowEventListResponse,
    WorkflowRunDetailsResponse,
    WorkflowRunListResponse,
    WorkflowRunStatus,
)
from app.core.container import workflow_run_repository
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


def _get_workflow_run_or_404(thread_id: str) -> WorkflowRunDetailsResponse:
    workflow_run = workflow_run_repository.get_workflow_run(thread_id)
    if not workflow_run:
        raise HTTPException(status_code=404, detail=f"Workflow run not found: {thread_id}")
    return workflow_run


def _validate_events_cursor(cursor: str) -> None:
    timestamp_raw, event_id = cursor.split("|", 1)
    try:
        datetime.fromisoformat(timestamp_raw.replace("Z", "+00:00"))
        UUID(event_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor format") from exc


@router.get("", response_model=WorkflowRunListResponse)
async def list_workflows(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100, alias="page_size")] = 10,
    page_size_legacy: Annotated[int | None, Query(ge=1, le=100, alias="pageSize")] = (None),
    status: Annotated[WorkflowRunStatus | None, Query()] = None,
) -> WorkflowRunListResponse:
    effective_page_size = page_size_legacy if page_size_legacy is not None else page_size
    items, total = workflow_run_repository.list_workflow_runs(
        page=page,
        page_size=effective_page_size,
        status=status,
    )
    return WorkflowRunListResponse(
        items=items, page=page, page_size=effective_page_size, total=total
    )


@router.get("/{thread_id}", response_model=WorkflowRunDetailsResponse)
async def get_workflow(thread_id: str) -> WorkflowRunDetailsResponse:
    return _get_workflow_run_or_404(thread_id)


@router.get("/{thread_id}/events", response_model=WorkflowEventListResponse)
async def list_workflow_events(
    thread_id: str,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query()] = None,
) -> WorkflowEventListResponse:
    if cursor:
        if "|" not in cursor:
            raise HTTPException(status_code=400, detail="Invalid cursor format")
        _validate_events_cursor(cursor)

    _get_workflow_run_or_404(thread_id)

    items, next_cursor, has_more = workflow_run_repository.list_workflow_events(
        thread_id=thread_id,
        limit=limit,
        cursor=cursor,
    )
    return WorkflowEventListResponse(
        items=items,
        pagination=CursorPagination(
            limit=limit,
            next_cursor=next_cursor,
            has_more=has_more,
        ),
    )
