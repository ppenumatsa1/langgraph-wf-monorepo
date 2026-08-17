from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class UnderwritingState(TypedDict, total=False):
    workflow_run_id: str
    application: dict[str, Any]
    application_id: str
    applicant_name: str
    fail_risk_once: bool
    fail_credit_randomly: bool
    crash_after_executor: str | None
    expected_checks: list[str]
    check_results: Annotated[list[dict[str, Any]], operator.add]
    final_decision: dict[str, Any]
