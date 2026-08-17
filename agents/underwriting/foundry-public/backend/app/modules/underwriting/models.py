from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
from typing import Any


class CheckType(StrEnum):
    RISK = "risk"
    CREDIT = "credit"
    MEDICAL = "medical"
    DRIVING = "driving"


class Decision(StrEnum):
    APPROVED = "APPROVED"
    APPROVED_WITH_CONDITIONS = "APPROVED_WITH_CONDITIONS"
    REFER_TO_HUMAN_UNDERWRITER = "REFER_TO_HUMAN_UNDERWRITER"
    DECLINED = "DECLINED"


@dataclass(slots=True)
class UnderwritingApplication:
    application_id: str
    applicant_name: str
    age: int
    income: float
    requested_coverage: float
    health_disclosures: str
    driving_history: str
    credit_score: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class UnderwritingRunRequest:
    workflow_run_id: str
    application: UnderwritingApplication


@dataclass(slots=True)
class CheckRequest:
    workflow_run_id: str
    application: UnderwritingApplication
    check_type: CheckType

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["check_type"] = self.check_type.value
        return payload


@dataclass(slots=True)
class CheckResult:
    workflow_run_id: str
    application_id: str
    check_type: CheckType
    score: float
    details: dict[str, Any]
    idempotency_key: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["check_type"] = self.check_type.value
        return payload


@dataclass(slots=True)
class AllChecksComplete:
    workflow_run_id: str
    application_id: str


@dataclass(slots=True)
class FinalDecisionResult:
    workflow_run_id: str
    application_id: str
    decision: Decision
    rationale: str
    score_breakdown: dict[str, Any]
    idempotency_key: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["decision"] = self.decision.value
        return payload
