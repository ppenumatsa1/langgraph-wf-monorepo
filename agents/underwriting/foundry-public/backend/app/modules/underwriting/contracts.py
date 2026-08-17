from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol

from app.modules.underwriting.models import Decision


class DecisionLLMClient(Protocol):
    async def generate_rationale(
        self,
        *,
        decision: Decision,
        average_score: float,
        score_breakdown: Mapping[str, float],
    ) -> str: ...
