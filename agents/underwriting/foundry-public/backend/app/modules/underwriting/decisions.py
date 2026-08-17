from __future__ import annotations

from collections.abc import Mapping

from app.modules.underwriting.contracts import DecisionLLMClient
from app.modules.underwriting.models import Decision


def compute_decision(avg_score: float, child_scores: Mapping[str, float]) -> Decision:
    risk = child_scores.get("risk", 0.0)
    credit = child_scores.get("credit", 0.0)
    if avg_score >= 0.8 and risk >= 0.6 and credit >= 0.65:
        return Decision.APPROVED
    if avg_score >= 0.65:
        return Decision.APPROVED_WITH_CONDITIONS
    if avg_score >= 0.45:
        return Decision.REFER_TO_HUMAN_UNDERWRITER
    return Decision.DECLINED


async def build_final_rationale(
    *,
    decision: Decision,
    average_score: float,
    score_breakdown: Mapping[str, float],
    llm_client: DecisionLLMClient | None,
) -> str:
    if llm_client is None:
        return f"Decision based on average check score {average_score:.3f}"
    try:
        return await llm_client.generate_rationale(
            decision=decision,
            average_score=average_score,
            score_breakdown=score_breakdown,
        )
    except Exception:
        return f"Decision based on average check score {average_score:.3f}"
