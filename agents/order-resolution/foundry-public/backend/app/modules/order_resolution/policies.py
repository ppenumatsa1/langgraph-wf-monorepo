from __future__ import annotations

from dataclasses import dataclass

POLICY_RULES: dict[str, str] = {
    "late_delivery": "refund_allowed_if_delay_exceeds_3_days",
    "damaged_item": "replacement_or_full_refund_with_photo_proof",
    "wrong_item": "free_replacement_and_return_label",
}


@dataclass(frozen=True)
class PolicySeed:
    issue_type: str
    title: str
    content: str


def get_policy_for_issue(issue_type: str) -> str:
    return POLICY_RULES.get(issue_type, "manual_review_required")


def default_policy_seeds() -> list[PolicySeed]:
    return [
        PolicySeed(
            issue_type=issue_type,
            title=f"Policy: {issue_type.replace('_', ' ').title()}",
            content=f"Issue type '{issue_type}' should follow policy '{policy}'.",
        )
        for issue_type, policy in POLICY_RULES.items()
    ]
