from __future__ import annotations

from app.modules.order_resolution.models import WorkflowEvent
from app.modules.order_resolution.ports import WorkflowRunRepositoryPort


def status_from_output(event: WorkflowEvent) -> str | None:
    status = event.payload.get("status")
    if not isinstance(status, str):
        return None
    if status in {"completed", "failed", "escalated"}:
        return status
    return None


class WorkflowRunEventProjector:
    def __init__(self, workflow_run_repository: WorkflowRunRepositoryPort) -> None:
        self._workflow_run_repository = workflow_run_repository

    def sync_event_to_run(self, event: WorkflowEvent) -> None:
        self._workflow_run_repository.append_workflow_event(event.thread_id, event)

        if event.type == "workflow.stage":
            stage = event.payload.get("agent")
            if isinstance(stage, str):
                self._workflow_run_repository.update_current_stage(event.thread_id, stage)

        if event.type == "hitl.request":
            self._workflow_run_repository.add_pending_approval(event.thread_id, event.payload)
            self._workflow_run_repository.update_workflow_status(
                event.thread_id, "waiting_approval"
            )
            return

        if event.type == "hitl.response":
            checkpoint_id = event.payload.get("checkpoint_id")
            decision = event.payload.get("decision")
            reviewer = event.payload.get("reviewer")
            comments = event.payload.get("comments")
            if isinstance(checkpoint_id, str) and isinstance(decision, str):
                self._workflow_run_repository.resolve_approval(
                    thread_id=event.thread_id,
                    checkpoint_id=checkpoint_id,
                    decision=decision,
                    comment=comments if isinstance(comments, str) else None,
                    reviewer=reviewer if isinstance(reviewer, str) else None,
                )
            self._workflow_run_repository.update_workflow_status(event.thread_id, "running")
            return

        if event.type == "workflow.output":
            self._workflow_run_repository.update_latest_output(event.thread_id, event.payload)
            output_status = status_from_output(event)
            if output_status:
                self._workflow_run_repository.update_workflow_status(event.thread_id, output_status)
            else:
                self._workflow_run_repository.update_workflow_status(event.thread_id, "completed")
            return

        if event.type == "workflow.failed":
            self._workflow_run_repository.update_workflow_status(event.thread_id, "failed")
