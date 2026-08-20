from __future__ import annotations

from app.modules.order_resolution.models import WorkflowEvent
from app.modules.order_resolution.models import utc_now_iso as _utc_now_iso


def utc_now_iso() -> str:
    return _utc_now_iso()


__all__ = ["WorkflowEvent", "utc_now_iso"]
