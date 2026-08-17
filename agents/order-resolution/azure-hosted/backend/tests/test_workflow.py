from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from app.api.v1.schemas.chat import ChatRunRequest
from app.core.database import postgres_db
from app.infrastructure.events import EventBus
from app.infrastructure.mcp import MCPKnowledgeTool
from app.infrastructure.persistence import (
    CheckpointStore,
    IdempotencyStore,
    PostgresSessionMemoryStore,
    WorkflowRunRepository,
)
from app.infrastructure.rag.providers.noop_provider import NoopRAGProvider
from app.langgraph import (
    AzureTriageModel,
    LangGraphOrderResolutionWorkflow,
    PostgresCheckpointerFactory,
)
from app.langgraph.nodes import NodeDependencies
from app.modules.order_resolution.models import (
    ConcurrentStartError,
    PendingApprovalError,
    WorkflowContext,
)
from app.modules.order_resolution.projections import WorkflowRunEventProjector
from app.modules.order_resolution.service import OrderResolutionService
from app.sql.retention import prune_completed_checkpoints
from langgraph.types import Command


def _runtime() -> tuple[
    LangGraphOrderResolutionWorkflow,
    WorkflowRunRepository,
    CheckpointStore,
]:
    repository = WorkflowRunRepository()
    interrupt_repository = CheckpointStore()
    event_bus = EventBus()
    event_bus.add_listener(WorkflowRunEventProjector(repository).sync_event_to_run)
    workflow = LangGraphOrderResolutionWorkflow(
        event_bus=event_bus,
        memory_store=PostgresSessionMemoryStore(),
        interrupt_repository=interrupt_repository,
        workflow_run_repository=repository,
        checkpointer_factory=PostgresCheckpointerFactory(postgres_db.database_url),
        node_dependencies=NodeDependencies(
            triage_model=AzureTriageModel(),
            rag_provider=NoopRAGProvider(),
            mcp_tool=MCPKnowledgeTool(endpoint=None),
            idempotency_store=IdempotencyStore(),
            retry_attempts=1,
            retry_delay_seconds=0,
        ),
    )
    return workflow, repository, interrupt_repository


async def _start(message: str):
    workflow, repository, interrupts = _runtime()
    thread_id = str(uuid4())
    run_id = str(uuid4())
    repository.create_workflow_run(
        thread_id=thread_id,
        input_text=message,
        session_id=thread_id,
        customer_id="test-customer",
    )
    await workflow.start(
        WorkflowContext(
            run_id=run_id,
            thread_id=thread_id,
            session_id=thread_id,
            customer_id="test-customer",
            user_message=message,
        )
    )
    return workflow, repository, interrupts, thread_id, run_id


@pytest.mark.asyncio
async def test_low_risk_graph_completes_without_interrupt() -> None:
    workflow, repository, _, thread_id, _ = await _start("Order ORD-1001 arrived one day late.")

    details = repository.get_workflow_run(thread_id)

    assert details is not None
    assert details.status == "completed"
    assert [event.type for event in details.events] == [
        "workflow.stage",
        "workflow.stage",
        "workflow.stage",
        "workflow.stage",
        "tool.call",
        "workflow.stage",
        "workflow.output",
    ]
    assert details.latest_output["submission_id"].endswith("ord-1001")
    await workflow.shutdown()


@pytest.mark.asyncio
async def test_postgres_checkpoint_survives_recompile_and_process_restart() -> None:
    workflow, repository, interrupts, thread_id, _ = await _start(
        "Order ORD-1009 is delayed by five days."
    )
    waiting = repository.get_workflow_run(thread_id)
    assert waiting is not None
    assert waiting.status == "waiting_approval"
    checkpoint_id = waiting.pending_approvals[0].checkpoint_id
    mapping = interrupts.get(checkpoint_id)
    assert mapping is not None
    assert mapping["thread_id"] == thread_id
    assert mapping["langgraph_checkpoint_id"]
    assert mapping["interrupt_id"]
    assert "state" not in mapping
    assert waiting.pending_approvals[0].action is None
    assert waiting.pending_approvals[0].order_id is None
    assert waiting.pending_approvals[0].amount is None

    await workflow.shutdown()
    restarted_workflow, restarted_repository, _ = _runtime()
    resumed_thread = await restarted_workflow.handle_hitl_response(
        checkpoint_id=checkpoint_id,
        decision="approve",
        reviewer="restart-test",
        comments="approved after process restart",
    )

    assert resumed_thread == thread_id
    completed = restarted_repository.get_workflow_run(thread_id)
    assert completed is not None
    assert completed.status == "completed"
    assert [event.type for event in completed.events][-2:] == [
        "hitl.response",
        "workflow.output",
    ]
    await restarted_workflow.shutdown()


@pytest.mark.asyncio
async def test_duplicate_decision_is_atomic_and_submission_is_idempotent() -> None:
    workflow, repository, interrupts, thread_id, _ = await _start(
        "Order ORD-1004 arrived damaged and broken."
    )
    waiting = repository.get_workflow_run(thread_id)
    assert waiting is not None
    checkpoint_id = waiting.pending_approvals[0].checkpoint_id

    await workflow.handle_hitl_response(
        checkpoint_id=checkpoint_id,
        decision="approve",
        reviewer="reviewer",
        comments="approved",
    )
    before = repository.get_workflow_run(thread_id)
    assert before is not None
    before_event_ids = [event.id for event in before.events]

    await workflow.shutdown()
    restarted_workflow, restarted_repository, _ = _runtime()
    await restarted_workflow.handle_hitl_response(
        checkpoint_id=checkpoint_id,
        decision="approve",
        reviewer="reviewer",
        comments="duplicate",
    )
    after = restarted_repository.get_workflow_run(thread_id)

    assert after is not None
    assert [event.id for event in after.events] == before_event_ids
    assert [event.type for event in after.events].count("checkpoint.created") == 1
    assert [event.type for event in after.events].count("hitl.request") == 1
    assert interrupts.get(checkpoint_id)["status"] == "approved"
    with pytest.raises(ValueError, match="different decision"):
        await restarted_workflow.handle_hitl_response(
            checkpoint_id=checkpoint_id,
            decision="reject",
            reviewer="reviewer",
            comments="conflict",
        )
    await restarted_workflow.shutdown()


@pytest.mark.asyncio
async def test_rejection_escalates_and_does_not_submit() -> None:
    workflow, repository, _, thread_id, _ = await _start("Order ORD-1004 arrived damaged.")
    waiting = repository.get_workflow_run(thread_id)
    checkpoint_id = waiting.pending_approvals[0].checkpoint_id

    await workflow.handle_hitl_response(
        checkpoint_id=checkpoint_id,
        decision="reject",
        reviewer="reviewer",
        comments="manual review",
    )

    details = repository.get_workflow_run(thread_id)
    assert details is not None
    assert details.status == "escalated"
    assert "submission_id" not in details.latest_output
    await workflow.shutdown()


@pytest.mark.asyncio
async def test_high_risk_rejection_escalates_and_does_not_submit() -> None:
    workflow, repository, _, thread_id, _ = await _start("Order ORD-1009 is delayed by five days.")
    waiting = repository.get_workflow_run(thread_id)
    checkpoint_id = waiting.pending_approvals[0].checkpoint_id

    await workflow.handle_hitl_response(
        checkpoint_id=checkpoint_id,
        decision="reject",
        reviewer="reviewer",
        comments="reject high-risk refund",
    )

    details = repository.get_workflow_run(thread_id)
    assert details is not None
    assert details.status == "escalated"
    assert details.latest_output["status"] == "escalated"
    assert "submission_id" not in details.latest_output
    await workflow.shutdown()


@pytest.mark.asyncio
async def test_explanation_uses_durable_conversation_history() -> None:
    workflow, repository, _, thread_id, _ = await _start("Order ORD-1001 arrived late.")
    explanation_run_id = str(uuid4())
    await workflow.start(
        WorkflowContext(
            run_id=explanation_run_id,
            thread_id=thread_id,
            session_id=thread_id,
            customer_id="test-customer",
            user_message="Why was that resolution selected?",
        )
    )

    details = repository.get_workflow_run(thread_id)

    assert details is not None
    assert details.latest_output["status"] == "completed"
    assert "policy refund_allowed_if_delay_exceeds_3_days" in details.latest_output["message"]
    assert any(
        event.type == "workflow.stage" and event.payload.get("agent") == "explanation"
        for event in details.events
    )
    await workflow.shutdown()


@pytest.mark.asyncio
async def test_new_normal_message_is_rejected_while_thread_is_interrupted() -> None:
    workflow, repository, _, thread_id, _ = await _start("Order ORD-1009 is delayed.")
    service = OrderResolutionService(
        workflow=workflow,
        workflow_run_repository=repository,
    )

    with pytest.raises(PendingApprovalError):
        await service.start_chat_run(
            ChatRunRequest(
                thread_id=thread_id,
                message="Start a different normal request.",
            )
        )

    details = repository.get_workflow_run(thread_id)
    assert details is not None
    assert len([event for event in details.events if event.type == "hitl.request"]) == 1
    await workflow.shutdown()


@pytest.mark.asyncio
async def test_concurrent_same_thread_start_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow, repository, _ = _runtime()
    thread_id = str(uuid4())
    repository.create_workflow_run(
        thread_id=thread_id,
        input_text="concurrent start",
        session_id=thread_id,
    )
    entered = asyncio.Event()
    release = asyncio.Event()

    async def assert_start(_: str) -> None:
        return None

    async def invoke(*args, **kwargs):
        entered.set()
        await release.wait()
        return {}

    monkeypatch.setattr(workflow, "assert_thread_can_start", assert_start)
    monkeypatch.setattr(workflow, "_invoke", invoke)
    first = asyncio.create_task(
        workflow.start(
            WorkflowContext(
                run_id=str(uuid4()),
                thread_id=thread_id,
                session_id=thread_id,
                customer_id="test-customer",
                user_message="first",
            )
        )
    )
    await entered.wait()

    with pytest.raises(ConcurrentStartError):
        await workflow.start(
            WorkflowContext(
                run_id=str(uuid4()),
                thread_id=thread_id,
                session_id=thread_id,
                customer_id="test-customer",
                user_message="second",
            )
        )

    release.set()
    await first
    await workflow.shutdown()


@pytest.mark.asyncio
async def test_concurrent_same_thread_resume_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow, repository, _ = _runtime()
    thread_id = str(uuid4())
    run_id = str(uuid4())
    repository.create_workflow_run(
        thread_id=thread_id,
        input_text="Order ORD-1009 is delayed.",
        session_id=thread_id,
        customer_id="test-customer",
    )
    await workflow.start(
        WorkflowContext(
            run_id=run_id,
            thread_id=thread_id,
            session_id=thread_id,
            customer_id="test-customer",
            user_message="Order ORD-1009 is delayed.",
        )
    )
    checkpoint_id = repository.get_workflow_run(thread_id).pending_approvals[0].checkpoint_id
    entered = asyncio.Event()
    release = asyncio.Event()
    invoke = workflow._invoke

    async def blocking_invoke(*args, **kwargs):
        entered.set()
        await release.wait()
        return await invoke(*args, **kwargs)

    monkeypatch.setattr(workflow, "_invoke", blocking_invoke)
    first = asyncio.create_task(
        workflow.handle_hitl_response(
            checkpoint_id,
            "approve",
            "first-reviewer",
            "first response",
        )
    )
    await entered.wait()

    with pytest.raises(ConcurrentStartError):
        await workflow.handle_hitl_response(
            checkpoint_id,
            "approve",
            "second-reviewer",
            "duplicate response",
        )

    release.set()
    assert await first == thread_id
    await workflow.shutdown()


@pytest.mark.asyncio
async def test_cross_runtime_same_decision_claim_resumes_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_workflow, repository, _, thread_id, _ = await _start(
        "Order ORD-1009 is delayed by five days."
    )
    second_workflow, _, _ = _runtime()
    checkpoint_id = repository.get_workflow_run(thread_id).pending_approvals[0].checkpoint_id
    entered = asyncio.Event()
    release = asyncio.Event()
    first_invoke = first_workflow._invoke
    second_invoke = second_workflow._invoke
    invoke_count = 0

    async def blocking_first_invoke(*args, **kwargs):
        nonlocal invoke_count
        invoke_count += 1
        entered.set()
        await release.wait()
        return await first_invoke(*args, **kwargs)

    async def counted_second_invoke(*args, **kwargs):
        nonlocal invoke_count
        invoke_count += 1
        return await second_invoke(*args, **kwargs)

    monkeypatch.setattr(first_workflow, "_invoke", blocking_first_invoke)
    monkeypatch.setattr(second_workflow, "_invoke", counted_second_invoke)
    first = asyncio.create_task(
        first_workflow.handle_hitl_response(
            checkpoint_id,
            "approve",
            "first-reviewer",
            "first response",
        )
    )
    await entered.wait()

    assert (
        await asyncio.wait_for(
            second_workflow.handle_hitl_response(
                checkpoint_id,
                "approve",
                "second-reviewer",
                "duplicate response",
            ),
            timeout=5,
        )
        == thread_id
    )
    assert invoke_count == 1

    release.set()
    assert await first == thread_id
    assert invoke_count == 1
    await first_workflow.shutdown()
    await second_workflow.shutdown()


@pytest.mark.asyncio
async def test_failed_resume_releases_claim_for_immediate_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workflow, repository, interrupts, thread_id, _ = await _start(
        "Order ORD-1009 is delayed by five days."
    )
    checkpoint_id = repository.get_workflow_run(thread_id).pending_approvals[0].checkpoint_id
    invoke = workflow._invoke
    attempts = 0

    async def fail_once(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("transient resume failure")
        return await invoke(*args, **kwargs)

    monkeypatch.setattr(workflow, "_invoke", fail_once)
    with pytest.raises(RuntimeError, match="transient resume failure"):
        await workflow.handle_hitl_response(
            checkpoint_id,
            "approve",
            "first-reviewer",
            "first attempt",
        )

    assert interrupts.get(checkpoint_id)["status"] == "pending"
    assert (
        await workflow.handle_hitl_response(
            checkpoint_id,
            "approve",
            "retry-reviewer",
            "retry",
        )
        == thread_id
    )
    assert interrupts.get(checkpoint_id)["status"] == "approved"
    await workflow.shutdown()


@pytest.mark.asyncio
async def test_expired_resume_claim_can_be_recovered_after_process_crash() -> None:
    workflow, repository, interrupts, thread_id, _ = await _start(
        "Order ORD-1009 is delayed by five days."
    )
    checkpoint_id = repository.get_workflow_run(thread_id).pending_approvals[0].checkpoint_id
    claim = interrupts.begin_resolution(
        checkpoint_id=checkpoint_id,
        decision="approve",
        reviewer="crashed-reviewer",
        comments="process terminated before resume",
    )
    assert claim["should_resume"] is True
    with postgres_db.get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE workflow_interrupts
                SET updated_at = NOW() - INTERVAL '6 minutes'
                WHERE checkpoint_id = %s::uuid
                """,
                (checkpoint_id,),
            )
    await workflow.shutdown()

    restarted, _, restarted_interrupts = _runtime()
    assert (
        await restarted.handle_hitl_response(
            checkpoint_id,
            "approve",
            "recovery-reviewer",
            "recover expired claim",
        )
        == thread_id
    )
    assert restarted_interrupts.get(checkpoint_id)["status"] == "approved"
    await restarted.shutdown()


@pytest.mark.asyncio
async def test_concurrent_local_idempotency_retry_submits_once() -> None:
    workflow, repository, _ = _runtime()
    service = OrderResolutionService(
        workflow=workflow,
        workflow_run_repository=repository,
    )
    request = ChatRunRequest(
        message="Order ORD-1001 arrived one day late.",
        thread_id=str(uuid4()),
        idempotency_key=f"concurrent-{uuid4()}",
    )

    first, second = await asyncio.gather(
        service.start_chat_run(request),
        service.start_chat_run(request),
    )

    assert first.run_id == second.run_id
    assert first.thread_id == second.thread_id
    details = repository.get_workflow_run(first.thread_id)
    assert details is not None
    assert [event.type for event in details.events].count("workflow.output") == 1
    with postgres_db.get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS count
                FROM idempotency_keys
                WHERE workflow_run_id = %s
                  AND step_name = 'submit_resolution'
                  AND status = 'completed'
                """,
                (first.run_id,),
            )
            assert int(cur.fetchone()["count"]) == 1
    await workflow.shutdown()


@pytest.mark.asyncio
async def test_reconciliation_repairs_graph_interrupt_missing_projection() -> None:
    workflow, repository, interrupts, thread_id, _ = await _start("Order ORD-1009 is delayed.")
    waiting = repository.get_workflow_run(thread_id)
    checkpoint_id = waiting.pending_approvals[0].checkpoint_id
    with postgres_db.get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM workflow_events "
                "WHERE thread_id = %s AND type IN ('checkpoint.created', 'hitl.request')",
                (thread_id,),
            )
            cur.execute(
                "DELETE FROM workflow_interrupts WHERE checkpoint_id = %s::uuid",
                (checkpoint_id,),
            )
            cur.execute(
                "UPDATE workflow_runs SET status = 'running' WHERE thread_id = %s",
                (thread_id,),
            )

    result = await workflow.reconcile_thread(thread_id)
    repaired = repository.get_workflow_run(thread_id)

    assert result.graph_status == "interrupted"
    assert result.repaired is True
    assert interrupts.get(checkpoint_id)["status"] == "pending"
    assert repaired.status == "waiting_approval"
    assert [event.type for event in repaired.events].count("hitl.request") == 1
    await workflow.shutdown()


@pytest.mark.asyncio
async def test_reconciliation_replaces_stale_projection_with_graph_truth() -> None:
    workflow, repository, interrupts, thread_id, _ = await _start("Order ORD-1009 is delayed.")
    waiting = repository.get_workflow_run(thread_id)
    authoritative_id = waiting.pending_approvals[0].checkpoint_id
    stale_id = str(uuid4())
    with postgres_db.get_pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM workflow_interrupts WHERE checkpoint_id = %s::uuid",
                (authoritative_id,),
            )
    interrupts.reconcile_pending(
        checkpoint_id=stale_id,
        thread_id=thread_id,
        langgraph_checkpoint_id="stale-checkpoint",
        langgraph_checkpoint_ns="",
        interrupt_id="stale-interrupt",
        audit_summary={"reconciliation": "test-stale-row"},
    )

    result = await workflow.reconcile_thread(thread_id)

    assert result.repaired is True
    assert interrupts.get(authoritative_id)["status"] == "pending"
    assert interrupts.get(stale_id)["status"] == "orphaned"
    assert (
        repository.get_workflow_run(thread_id).pending_approvals[0].checkpoint_id
        == authoritative_id
    )
    await workflow.shutdown()


@pytest.mark.asyncio
async def test_reconciliation_finishes_terminal_crash_window() -> None:
    workflow, repository, interrupts, thread_id, _ = await _start("Order ORD-1009 is delayed.")
    waiting = repository.get_workflow_run(thread_id)
    checkpoint_id = waiting.pending_approvals[0].checkpoint_id
    interrupts.begin_resolution(
        checkpoint_id=checkpoint_id,
        decision="approve",
        reviewer="crash-test",
        comments="resume committed before projection",
    )
    graph = await workflow._get_graph()
    await graph.ainvoke(
        Command(
            resume={
                "decision": "approve",
                "reviewer": "crash-test",
                "comments": "resume committed before projection",
            }
        ),
        {"configurable": {"thread_id": thread_id}},
    )
    assert interrupts.get(checkpoint_id)["status"] == "resuming"
    assert repository.get_workflow_run(thread_id).latest_output is None
    await workflow.shutdown()

    restarted, restarted_repository, restarted_interrupts = _runtime()
    result = await restarted.reconcile_thread(thread_id)
    details = restarted_repository.get_workflow_run(thread_id)

    assert result.graph_status == "completed"
    assert restarted_interrupts.get(checkpoint_id)["status"] == "approved"
    assert details.status == "completed"
    assert details.latest_output["submission_id"].endswith("ord-1009")
    await restarted.shutdown()


@pytest.mark.asyncio
async def test_reconciliation_marks_projection_orphan_when_graph_is_missing() -> None:
    workflow, repository, interrupts = _runtime()
    thread_id = str(uuid4())
    checkpoint_id = str(uuid4())
    repository.create_workflow_run(
        thread_id=thread_id,
        input_text="orphaned approval",
        session_id=thread_id,
    )
    interrupts.reconcile_pending(
        checkpoint_id=checkpoint_id,
        thread_id=thread_id,
        langgraph_checkpoint_id="missing",
        langgraph_checkpoint_ns="",
        interrupt_id="missing",
        audit_summary={"reconciliation": "test-orphan"},
    )
    repository.add_pending_approval(thread_id, {"checkpoint_id": checkpoint_id})
    repository.update_workflow_status(thread_id, "waiting_approval")

    result = await workflow.reconcile_thread(thread_id)
    details = repository.get_workflow_run(thread_id)

    assert result.graph_status == "orphaned"
    assert interrupts.get(checkpoint_id)["status"] == "orphaned"
    assert details.status == "failed"
    assert details.pending_approvals == []
    await workflow.shutdown()


@pytest.mark.asyncio
async def test_checkpoint_retention_executes_and_preserves_unresolved_threads() -> None:
    terminal_workflow, _, _, terminal_thread, _ = await _start(
        "Order ORD-1001 arrived one day late."
    )
    pending_workflow, _, _, pending_thread, _ = await _start(
        "Order ORD-1009 is delayed by five days."
    )
    try:
        with postgres_db.get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE workflow_runs
                    SET status = 'completed',
                        completed_at = NOW() - INTERVAL '200 years'
                    WHERE thread_id IN (%s, %s)
                    """,
                    (terminal_thread, pending_thread),
                )
                cur.execute(
                    """
                    SELECT thread_id, COUNT(*) AS checkpoint_count
                    FROM checkpoints
                    WHERE thread_id IN (%s, %s)
                    GROUP BY thread_id
                    """,
                    (terminal_thread, pending_thread),
                )
                before = {
                    str(row["thread_id"]): int(row["checkpoint_count"]) for row in cur.fetchall()
                }
        assert before[terminal_thread] > 0
        assert before[pending_thread] > 0

        deleted = await asyncio.to_thread(
            prune_completed_checkpoints,
            36500,
        )

        with postgres_db.get_pool().connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT thread_id, COUNT(*) AS checkpoint_count
                    FROM checkpoints
                    WHERE thread_id IN (%s, %s)
                    GROUP BY thread_id
                    """,
                    (terminal_thread, pending_thread),
                )
                after = {
                    str(row["thread_id"]): int(row["checkpoint_count"]) for row in cur.fetchall()
                }
        assert deleted["checkpoints"] >= before[terminal_thread]
        assert terminal_thread not in after
        assert after[pending_thread] == before[pending_thread]
    finally:
        await terminal_workflow.shutdown()
        await pending_workflow.shutdown()
