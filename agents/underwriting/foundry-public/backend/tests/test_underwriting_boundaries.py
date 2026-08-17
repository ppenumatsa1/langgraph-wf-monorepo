from __future__ import annotations

import asyncio

from app.core.config import Settings
from app.modules.underwriting.models import UnderwritingApplication
from app.modules.underwriting.ports import WorkflowRunAlreadyClaimedError
from app.modules.underwriting.projections import (
    build_safe_selected_run_context,
    project_workflow_run,
)
from app.modules.underwriting.service import UnderwritingService


def _settings(*, execution_mode: str = "local") -> Settings:
    return Settings(
        db_host="",
        db_port=0,
        db_name="",
        db_user="",
        db_password="",
        log_level="WARNING",
        fail_risk_once=False,
        fail_credit_randomly=False,
        crash_after_executor="",
        crash_after_step_or_superstep="",
        retry_max_attempts=3,
        retry_base_delay_ms=1,
        retry_jitter_ms=0,
        azure_ai_project_id="",
        azure_ai_project_name="",
        foundry_model_deployment_name="",
        azure_openai_endpoint="",
        azure_openai_api_key="",
        execution_mode=execution_mode,
    )


def _application() -> UnderwritingApplication:
    return UnderwritingApplication(
        application_id="app-boundary-001",
        applicant_name="Ada Lovelace",
        age=38,
        income=145000,
        requested_coverage=500000,
        health_disclosures="none",
        driving_history="clean",
        credit_score=760,
    )


class FakeWorkflow:
    def __init__(self) -> None:
        self.started: dict[str, object] | None = None

    async def startup(self) -> None:
        return None

    async def shutdown(self) -> None:
        return None

    async def start(self, **kwargs: object):
        self.started = dict(kwargs)
        return [
            {
                "workflow_run_id": str(kwargs["workflow_run_id"]),
                "application_id": "app-boundary-001",
                "decision": "APPROVED",
                "rationale": "Deterministic rationale",
                "score_breakdown": {"risk": 0.9},
                "idempotency_key": "result-key",
            }
        ]

    async def resume(self, _workflow_run_id: str):
        return []


class AlreadyClaimedWorkflow(FakeWorkflow):
    async def start(self, **kwargs: object):
        raise WorkflowRunAlreadyClaimedError(str(kwargs["workflow_run_id"]))


class FakeRepository:
    def __init__(self) -> None:
        self.run: dict[str, object] | None = None

    def get_workflow_run(self, _workflow_run_id: str):
        return self.run

    def list_underwriting_results(self, _workflow_run_id: str):
        return []

    def list_workflow_runs(self, *, search, status, limit, offset):
        return 0, []

    def list_business_state(self, _workflow_run_id: str):
        return []

    def list_events(self, _workflow_run_id: str):
        return []

    def list_checkpoints(self, _workflow_run_id: str):
        return []

    def get_safe_run_status(self, _workflow_run_id: str):
        return "COMPLETED"

    def list_safe_event_summaries(self, _workflow_run_id: str, *, limit: int):
        assert limit == 100
        return [
            {
                "event_type": "check_completed",
                "executor_name": "risk_score",
                "created_at": "2026-08-05T00:00:00Z",
            },
            {
                "event_type": "private_payload",
                "executor_name": "risk_score",
                "created_at": "2026-08-05T00:00:01Z",
            },
        ]

    def get_safe_checkpoint_summary(self, _workflow_run_id: str):
        return 1, "2026-08-05T00:00:02Z"

    def get_safe_final_decision(self, _workflow_run_id: str):
        return "APPROVED"


class RaceRepository(FakeRepository):
    def __init__(self) -> None:
        super().__init__()
        self.read_count = 0

    def get_workflow_run(self, _workflow_run_id: str):
        self.read_count += 1
        if self.read_count == 1:
            return None
        return {"status": "RUNNING"}


def test_public_service_starts_local_workflow_through_facade() -> None:
    workflow = FakeWorkflow()
    repository = FakeRepository()
    service = UnderwritingService(
        settings=_settings(),
        workflow=workflow,
        workflow_run_repository=repository,
    )

    projection = asyncio.run(
        service.start_run(
            workflow_run_id="run-boundary-001",
            application=_application(),
            fail_risk_once=False,
            fail_credit_randomly=False,
            crash_after_executor=None,
        )
    )

    assert workflow.started is not None
    assert workflow.started["application"] == _application().to_dict()
    assert workflow.started["fail_risk_once"] is False
    assert projection == {
        "workflow_run_id": "run-boundary-001",
        "status": "COMPLETED",
        "outputs": [
            {
                "workflow_run_id": "run-boundary-001",
                "application_id": "app-boundary-001",
                "decision": "APPROVED",
                "rationale": "Deterministic rationale",
                "score_breakdown": {"risk": 0.9},
                "idempotency_key": "result-key",
            }
        ],
    }


def test_public_service_projects_atomic_duplicate_start_without_executing() -> None:
    repository = RaceRepository()
    service = UnderwritingService(
        settings=_settings(),
        workflow=AlreadyClaimedWorkflow(),
        workflow_run_repository=repository,
    )

    projection = asyncio.run(
        service.start_run(
            workflow_run_id="run-boundary-001",
            application=_application(),
            fail_risk_once=False,
            fail_credit_randomly=False,
            crash_after_executor=None,
        )
    )

    assert projection == {
        "workflow_run_id": "run-boundary-001",
        "status": "RUNNING",
        "outputs": [],
    }


def test_project_workflow_run_prefers_persisted_status() -> None:
    repository = FakeRepository()
    repository.run = {"status": "CRASHED"}

    projection = project_workflow_run(
        repository,
        "run-boundary-001",
        fallback_status="COMPLETED",
        outputs=[
            {
                "workflow_run_id": "run-boundary-001",
                "application_id": "app-boundary-001",
                "decision": "APPROVED",
                "rationale": "Deterministic rationale",
                "score_breakdown": {"risk": 0.9},
                "idempotency_key": "result-key",
            }
        ],
    )

    assert projection["status"] == "CRASHED"


def test_safe_context_projection_filters_non_allowlisted_events() -> None:
    context = build_safe_selected_run_context(FakeRepository(), "run-boundary-001")

    assert context is not None
    assert [event.name for event in context.events] == ["check_completed"]
    assert context.to_dict() == {
        "workflow_run_id": "run-boundary-001",
        "status": "COMPLETED",
        "events": [
            {
                "name": "check_completed",
                "timestamp": "2026-08-05T00:00:00Z",
                "executor": "risk_score",
            }
        ],
        "checkpoints": {"count": 1, "latest_created_at": "2026-08-05T00:00:02Z"},
        "output": {"final_decision": "APPROVED"},
    }
