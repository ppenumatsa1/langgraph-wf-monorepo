from __future__ import annotations

from uuid import uuid4

from app.infrastructure.persistence import WorkflowRunRepository
from app.infrastructure.persistence.session_memory import SessionMemoryStore
from app.modules.order_resolution.models import WorkflowEvent


def test_audit_and_conversation_projections_reload_after_restart() -> None:
    thread_id = str(uuid4())
    run_repo = WorkflowRunRepository()
    memory_store = SessionMemoryStore()
    run_repo.create_workflow_run(
        thread_id=thread_id,
        input_text="Order ORD-1001 delayed",
        session_id=thread_id,
    )
    memory_store.append_message(
        thread_id,
        "user",
        "Order ORD-1001 delayed",
        dedupe_key="run:user",
    )
    memory_store.append_message(
        thread_id,
        "assistant",
        "Resolution complete",
        dedupe_key="run:assistant",
    )
    event = WorkflowEvent(
        type="workflow.stage",
        thread_id=thread_id,
        payload={"agent": "triage", "status": "completed"},
    )
    run_repo.append_workflow_event(thread_id, event)

    reloaded_run = WorkflowRunRepository().get_workflow_run(thread_id)
    reloaded_messages = SessionMemoryStore().get_messages(thread_id)

    assert reloaded_run is not None
    assert any(item.id == event.id for item in reloaded_run.events)
    assert [item["role"] for item in reloaded_messages] == ["user", "assistant"]
