from __future__ import annotations

import asyncio

from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository
from app.main import resume_workflow, run_workflow
from app.modules.underwriting.models import UnderwritingApplication


def test_crash_then_resume_from_latest_langgraph_checkpoint() -> None:
    run_id = "run-resume-001"
    app = UnderwritingApplication(
        application_id="app-resume-001",
        applicant_name="Resume Tester",
        age=37,
        income=135000,
        requested_coverage=600000,
        health_disclosures="none",
        driving_history="minor speed ticket",
        credit_score=720,
    )

    crashed = False
    try:
        asyncio.run(
            run_workflow(
                workflow_run_id=run_id,
                app=app,
                crash_after_executor="medical_check",
            )
        )
    except Exception:
        crashed = True
    assert crashed, "run should crash for this scenario"

    repo = WorkflowRunRepository()
    checkpoints_before = repo.list_checkpoints(run_id)
    assert checkpoints_before, "native LangGraph checkpoints should be projected"

    outputs = asyncio.run(resume_workflow(run_id))
    assert outputs, "resume should finish and produce outputs"
    checkpoints_after = repo.list_checkpoints(run_id)
    assert len(checkpoints_after) >= len(checkpoints_before)
    assert all(checkpoint.get("created_at") for checkpoint in checkpoints_after)
