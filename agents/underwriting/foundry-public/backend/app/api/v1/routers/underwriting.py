from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.api.v1.schemas.underwriting import RunHistoryResponse, RunResponse, StartRunRequest
from app.core.container import get_underwriting_service
from app.core.telemetry import annotate_current_span
from app.modules.underwriting.models import UnderwritingApplication
from app.modules.underwriting.service import UnderwritingService

router = APIRouter(prefix="/api/v1/underwriting", tags=["underwriting"])
service: UnderwritingService | None = None


def _service() -> UnderwritingService:
    return service or get_underwriting_service()


@router.post("/runs", response_model=RunResponse)
async def start_run(request: StartRunRequest) -> RunResponse:
    app = UnderwritingApplication(**request.application.model_dump())
    run_id = request.workflow_run_id or f"run-{uuid.uuid4().hex[:10]}"
    annotate_current_span(run_id, "start")
    try:
        projection = await _service().start_run(
            workflow_run_id=run_id,
            application=app,
            fail_risk_once=request.fail_risk_once,
            fail_credit_randomly=request.fail_credit_randomly,
            crash_after_executor=request.crash_after_executor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception:
        return RunResponse(
            workflow_run_id=run_id,
            status="CRASHED",
            outputs=[{"error": "Hosted workflow invocation failed"}],
        )
    return RunResponse(**projection)


@router.post("/runs/{run_id}/resume", response_model=RunResponse)
async def resume_run(run_id: str) -> RunResponse:
    annotate_current_span(run_id, "resume")
    try:
        projection = await _service().resume_run(run_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Hosted workflow invocation failed") from exc
    return RunResponse(**projection)


@router.get("/runs", response_model=RunHistoryResponse)
async def list_runs(
    search: str | None = Query(default=None, max_length=256),
    status: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> RunHistoryResponse:
    total, items = _service().list_runs(
        search=search,
        status=status,
        limit=limit,
        offset=offset,
    )
    return RunHistoryResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    run = _service().get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@router.get("/runs/{run_id}/state")
async def get_run_state(run_id: str) -> list[dict[str, Any]]:
    return _service().get_state(run_id)


@router.get("/runs/{run_id}/events")
async def get_run_events(run_id: str) -> list[dict[str, Any]]:
    return _service().get_events(run_id)


@router.get("/runs/{run_id}/checkpoints")
async def get_run_checkpoints(run_id: str) -> list[dict[str, Any]]:
    return _service().get_checkpoints(run_id)
