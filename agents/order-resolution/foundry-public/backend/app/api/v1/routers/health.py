from __future__ import annotations

import os

from app.api.v1.schemas.health import HealthResponse
from app.core.container import config
from app.langgraph.clients import triage_mode_metadata
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
@router.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    metadata = triage_mode_metadata()
    runtime_provider = metadata.get("provider", "unknown")
    runtime_mode = metadata.get("mode", "unknown")
    return HealthResponse(
        workflow_mode=config.workflow_mode,
        runtime_provider=runtime_provider,
        runtime_mode=runtime_mode,
        environment=os.getenv("APP_ENV", "local"),
    )
