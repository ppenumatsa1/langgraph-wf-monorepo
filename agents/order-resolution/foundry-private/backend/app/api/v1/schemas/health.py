from __future__ import annotations

from typing import Literal

from app.core.config import WorkflowMode
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "langgraph-order-resolution-foundry-private-backend"
    workflow_mode: WorkflowMode
    runtime_provider: str
    runtime_mode: str
    environment: str
