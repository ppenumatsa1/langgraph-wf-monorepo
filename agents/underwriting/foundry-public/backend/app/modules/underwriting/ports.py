from __future__ import annotations

from typing import Any, Protocol

from app.modules.underwriting.copilot import SafeRunExplanationRequest
from app.modules.underwriting.hosted import HostedWorkflowEnvelope


class WorkflowRunAlreadyClaimedError(RuntimeError):
    def __init__(self, workflow_run_id: str) -> None:
        super().__init__(f"workflow run already claimed: {workflow_run_id}")
        self.workflow_run_id = workflow_run_id


class UnderwritingWorkflowEngine(Protocol):
    async def startup(self) -> None: ...

    async def shutdown(self) -> None: ...

    async def start(
        self,
        *,
        workflow_run_id: str,
        application: dict[str, Any],
        fail_risk_once: bool,
        fail_credit_randomly: bool,
        crash_after_executor: str | None,
    ) -> list[dict[str, Any]]: ...

    async def resume(self, workflow_run_id: str) -> list[dict[str, Any]]: ...


class UnderwritingHostedWorkflowPort(Protocol):
    async def invoke(
        self,
        request_envelope: HostedWorkflowEnvelope | SafeRunExplanationRequest,
    ) -> dict[str, Any]: ...


class UnderwritingRunRepositoryPort(Protocol):
    def get_workflow_run(self, workflow_run_id: str) -> dict[str, Any] | None: ...

    def list_workflow_runs(
        self,
        *,
        search: str | None,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[int, list[dict[str, Any]]]: ...

    def list_business_state(self, workflow_run_id: str) -> list[dict[str, Any]]: ...

    def list_events(self, workflow_run_id: str) -> list[dict[str, Any]]: ...

    def list_checkpoints(self, workflow_run_id: str) -> list[dict[str, Any]]: ...

    def list_underwriting_results(self, workflow_run_id: str) -> list[dict[str, Any]]: ...

    def get_safe_run_status(self, workflow_run_id: str) -> str | None: ...

    def list_safe_event_summaries(
        self, workflow_run_id: str, *, limit: int
    ) -> list[dict[str, Any]]: ...

    def get_safe_checkpoint_summary(self, workflow_run_id: str) -> tuple[int, Any | None]: ...

    def get_safe_final_decision(self, workflow_run_id: str) -> str | None: ...
