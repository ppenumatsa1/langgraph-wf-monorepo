from __future__ import annotations

import asyncio

from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository
from app.main import resume_workflow, run_workflow
from app.modules.underwriting.models import UnderwritingApplication


def test_idempotency_prevents_duplicate_results_after_resume() -> None:
    run_id = "run-idem-001"
    app = UnderwritingApplication(
        application_id="app-idem-001",
        applicant_name="Idempotency Tester",
        age=45,
        income=100000,
        requested_coverage=550000,
        health_disclosures="none",
        driving_history="clean",
        credit_score=730,
    )

    try:
        asyncio.run(
            run_workflow(
                workflow_run_id=run_id,
                app=app,
                crash_after_executor="medical_check",
            )
        )
    except Exception:
        pass

    asyncio.run(resume_workflow(run_id))

    repo = WorkflowRunRepository()
    assert repo.count_underwriting_results_by_key("run-idem-001:risk_check:app-idem-001") == 1
    assert repo.count_underwriting_results_by_key("run-idem-001:credit_check:app-idem-001") == 1
    assert repo.count_underwriting_results_by_key("run-idem-001:medical_check:app-idem-001") == 1
    assert repo.count_underwriting_results_by_key("run-idem-001:driving_check:app-idem-001") == 1
    assert repo.count_underwriting_results_by_key("run-idem-001:final_decision:app-idem-001") == 1
