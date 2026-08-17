from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from app.modules.underwriting.copilot import (
    SAFE_EVENT_TYPES,
    SAFE_EXECUTOR_NAMES,
    SafeRunEvent,
    SafeSelectedRunContext,
    normalize_decision,
    normalize_status,
    normalize_timestamp,
)
from app.modules.underwriting.ports import UnderwritingRunRepositoryPort


def serialize_output(output: Any) -> Any:
    if isinstance(output, dict):
        return output
    if hasattr(output, "to_dict"):
        return output.to_dict()
    if is_dataclass(output):
        return asdict(output)
    if hasattr(output, "__dict__"):
        return dict(vars(output))
    return str(output)


def final_decision_outputs(
    repository: UnderwritingRunRepositoryPort,
    workflow_run_id: str,
) -> list[dict[str, Any]]:
    return [
        result["result_json"]
        for result in repository.list_underwriting_results(workflow_run_id)
        if result.get("check_type") == "final_decision"
        and isinstance(result.get("result_json"), dict)
    ]


def project_workflow_run(
    repository: UnderwritingRunRepositoryPort,
    workflow_run_id: str,
    *,
    fallback_status: str,
    outputs: list[Any] | None = None,
) -> dict[str, Any]:
    get_run = getattr(repository, "get_workflow_run", None)
    run = get_run(workflow_run_id) if callable(get_run) else None
    projected_outputs = (
        final_decision_outputs(repository, workflow_run_id)
        if outputs is None
        else [serialize_output(output) for output in outputs]
    )
    return {
        "workflow_run_id": workflow_run_id,
        "status": str(run.get("status") if run is not None else fallback_status),
        "outputs": projected_outputs,
    }


def build_safe_selected_run_context(
    repository: UnderwritingRunRepositoryPort,
    workflow_run_id: str,
) -> SafeSelectedRunContext | None:
    status = repository.get_safe_run_status(workflow_run_id)
    if status is None:
        return None

    events: list[SafeRunEvent] = []
    for event in repository.list_safe_event_summaries(workflow_run_id, limit=100):
        name = event.get("event_type")
        executor = event.get("executor_name")
        if name not in SAFE_EVENT_TYPES or executor not in SAFE_EXECUTOR_NAMES:
            continue
        events.append(
            SafeRunEvent(
                name=name,
                timestamp=normalize_timestamp(event.get("created_at")),
                executor=executor,
            )
        )

    checkpoint_count, latest_checkpoint_at = repository.get_safe_checkpoint_summary(workflow_run_id)
    return SafeSelectedRunContext(
        workflow_run_id=workflow_run_id,
        status=normalize_status(status),
        events=tuple(events),
        checkpoint_count=checkpoint_count,
        latest_checkpoint_at=normalize_timestamp(latest_checkpoint_at),
        final_decision=normalize_decision(repository.get_safe_final_decision(workflow_run_id)),
    )
