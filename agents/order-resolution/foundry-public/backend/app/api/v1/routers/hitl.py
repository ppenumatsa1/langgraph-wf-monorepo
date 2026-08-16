from __future__ import annotations

from app.api.v1.schemas.hitl import HitlResponseRequest, HitlResponseResult
from app.core.container import order_resolution_service
from app.infrastructure.persistence.idempotency_store import IdempotencyInProgressError
from app.modules.order_resolution.models import ConcurrentStartError
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/hitl", tags=["hitl"])


@router.post("/respond", response_model=HitlResponseResult)
async def respond_hitl(request: HitlResponseRequest) -> HitlResponseResult:
    try:
        return await order_resolution_service.respond_hitl(request)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IdempotencyInProgressError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc
    except ConcurrentStartError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
