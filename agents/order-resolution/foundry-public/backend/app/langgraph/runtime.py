from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from app.core.telemetry import current_trace_context, workflow_stage_span
from app.langgraph.checkpointer import CheckpointerFactory
from app.langgraph.factory import build_order_resolution_graph
from app.langgraph.nodes import NodeDependencies
from app.langgraph.state import OrderResolutionState
from app.modules.order_resolution.models import (
    ConcurrentStartError,
    PendingApprovalError,
    WorkflowContext,
    WorkflowEvent,
)
from app.modules.order_resolution.ports import (
    EventPublisher,
    InterruptRepository,
    SessionMemoryRepository,
    WorkflowRunRepositoryPort,
)

from langgraph.types import Command


@dataclass(frozen=True)
class ReconciliationResult:
    thread_id: str
    graph_status: str
    checkpoint_id: str | None = None
    repaired: bool = False


class LangGraphOrderResolutionWorkflow:
    def __init__(
        self,
        *,
        event_bus: EventPublisher,
        memory_store: SessionMemoryRepository,
        interrupt_repository: InterruptRepository,
        workflow_run_repository: WorkflowRunRepositoryPort,
        checkpointer_factory: CheckpointerFactory,
        node_dependencies: NodeDependencies,
    ) -> None:
        self._event_bus = event_bus
        self._memory_store = memory_store
        self._interrupt_repository = interrupt_repository
        self._workflow_run_repository = workflow_run_repository
        self._checkpointer_factory = checkpointer_factory
        self._node_dependencies = node_dependencies
        self._graph: Any | None = None
        self._graph_lock = asyncio.Lock()
        self._startup_lock = asyncio.Lock()
        self._thread_invoke_locks: dict[str, asyncio.Lock] = {}
        self._started = False

    async def startup(self) -> None:
        if self._started:
            return
        async with self._startup_lock:
            if self._started:
                return
            await self._get_graph()
            await self.reconcile_all()
            self._started = True

    async def shutdown(self) -> None:
        self._graph = None
        self._started = False
        self._thread_invoke_locks.clear()
        await self._checkpointer_factory.close()

    async def assert_thread_can_start(self, thread_id: str) -> None:
        await self.reconcile_thread(thread_id)
        pending = self._interrupt_repository.get_unresolved_for_thread(thread_id)
        if pending is not None:
            raise PendingApprovalError(
                thread_id=thread_id,
                checkpoint_id=str(pending["checkpoint_id"]),
            )

    async def start(self, context: WorkflowContext) -> None:
        lock = self._thread_invoke_locks.setdefault(context.thread_id, asyncio.Lock())
        if lock.locked():
            raise ConcurrentStartError(context.thread_id)
        async with lock:
            await self.assert_thread_can_start(context.thread_id)
            with workflow_stage_span(
                "run",
                {
                    "workflow.thread_id": context.thread_id,
                    "workflow.run_id": context.run_id,
                    "workflow.session_id": context.session_id,
                    "workflow.customer_id": context.customer_id,
                },
            ):
                history = self._memory_store.get_messages(context.thread_id)
                self._memory_store.append_message(
                    context.thread_id,
                    "user",
                    context.user_message,
                    dedupe_key=f"{context.run_id}:user",
                )
                initial_state: OrderResolutionState = {
                    "run_id": context.run_id,
                    "thread_id": context.thread_id,
                    "session_id": context.session_id,
                    "customer_id": context.customer_id,
                    "user_message": context.user_message,
                    "conversation_history": history,
                    "trace_context": current_trace_context(),
                    "events": [],
                }
                try:
                    await self._invoke(initial_state, thread_id=context.thread_id)
                except Exception as exc:
                    await self._publish_failure(context, exc)
                    raise

    async def handle_hitl_response(
        self,
        checkpoint_id: str,
        decision: str,
        reviewer: str,
        comments: str | None,
    ) -> str:
        normalized = decision.strip().lower()
        if normalized not in {"approve", "reject"}:
            raise ValueError("Decision must be approve or reject.")

        mapping = self._interrupt_repository.get(checkpoint_id)
        if mapping is None:
            await self.reconcile_all()
            mapping = self._interrupt_repository.get(checkpoint_id)
        if mapping is None:
            raise ValueError(f"Checkpoint not found: {checkpoint_id}")

        thread_id = str(mapping["thread_id"])
        lock = self._thread_invoke_locks.setdefault(thread_id, asyncio.Lock())
        if lock.locked():
            raise ConcurrentStartError(thread_id)
        async with lock:
            return await self._handle_hitl_response_locked(
                checkpoint_id=checkpoint_id,
                thread_id=thread_id,
                decision=normalized,
                reviewer=reviewer,
                comments=comments,
            )

    async def _handle_hitl_response_locked(
        self,
        *,
        checkpoint_id: str,
        thread_id: str,
        decision: str,
        reviewer: str,
        comments: str | None,
    ) -> str:
        await self.reconcile_thread(thread_id)
        mapping = self._interrupt_repository.get(checkpoint_id)
        if mapping is None:
            raise ValueError(f"Checkpoint not found: {checkpoint_id}")
        if mapping["status"] in {"approved", "rejected"}:
            if mapping.get("decision") not in {None, decision}:
                raise ValueError("Checkpoint was already resolved with a different decision.")
            return thread_id

        snapshot, interrupt_info = await self._authoritative_interrupt(thread_id)
        self._validate_resume_projection(
            checkpoint_id=checkpoint_id,
            mapping=mapping,
            interrupt_info=interrupt_info,
        )
        graph_state = dict(snapshot.values)
        self._validate_approval_business_state(graph_state)
        trace_context = graph_state.get("trace_context")
        claim = self._interrupt_repository.begin_resolution(
            checkpoint_id=checkpoint_id,
            decision=decision,
            reviewer=reviewer,
            comments=comments,
        )
        if not claim["should_resume"]:
            return thread_id

        with workflow_stage_span(
            "hitl_resume",
            {
                "workflow.thread_id": thread_id,
                "workflow.run_id": graph_state.get("run_id"),
                "workflow.session_id": graph_state.get("session_id"),
                "workflow.checkpoint_id": checkpoint_id,
                "workflow.order_id": graph_state["order"]["order_id"],
                "workflow.action": graph_state["action"],
                "workflow.amount": graph_state["amount"],
                "workflow.hitl.decision": decision,
            },
            parent_trace_context=(trace_context if isinstance(trace_context, dict) else None),
        ):
            result = await self._invoke(
                Command(
                    resume={
                        "decision": decision,
                        "reviewer": reviewer,
                        "comments": comments,
                    }
                ),
                thread_id=thread_id,
            )
        terminal_status = str(result.get("terminal_status") or "")
        if terminal_status not in {"completed", "escalated"}:
            raise RuntimeError(f"Resumed graph did not reach a terminal state: {terminal_status}")
        return thread_id

    async def reconcile_all(self) -> list[ReconciliationResult]:
        results: list[ReconciliationResult] = []
        for thread_id in self._interrupt_repository.list_reconciliation_thread_ids():
            results.append(await self.reconcile_thread(thread_id))
        return results

    async def reconcile_thread(
        self,
        thread_id: str,
    ) -> ReconciliationResult:
        graph = await self._get_graph()
        config = {"configurable": {"thread_id": thread_id}}
        snapshot = await graph.aget_state(config)
        values = dict(snapshot.values or {})
        interrupt_info = self._interrupt_from_snapshot(snapshot, values)
        unresolved = self._interrupt_repository.get_unresolved_for_thread(thread_id)

        if interrupt_info is not None:
            stale_ids = self._interrupt_repository.reconcile_pending(
                checkpoint_id=interrupt_info["checkpoint_id"],
                thread_id=thread_id,
                langgraph_checkpoint_id=interrupt_info["langgraph_checkpoint_id"],
                langgraph_checkpoint_ns=interrupt_info["langgraph_checkpoint_ns"],
                interrupt_id=interrupt_info["interrupt_id"],
                audit_summary={
                    "run_id": values.get("run_id"),
                    "session_id": values.get("session_id"),
                    "reconciliation": "authoritative_graph_interrupt",
                },
            )
            for stale_id in stale_ids:
                self._workflow_run_repository.remove_approval_projection(stale_id)
            self._workflow_run_repository.add_pending_approval(
                thread_id,
                {"checkpoint_id": interrupt_info["checkpoint_id"]},
            )
            self._workflow_run_repository.update_workflow_status(thread_id, "waiting_approval")
            await self._publish_new_events(values)
            return ReconciliationResult(
                thread_id=thread_id,
                graph_status="interrupted",
                checkpoint_id=interrupt_info["checkpoint_id"],
                repaired=(
                    unresolved is None
                    or str(unresolved["checkpoint_id"]) != interrupt_info["checkpoint_id"]
                    or bool(stale_ids)
                ),
            )

        terminal_status = str(values.get("terminal_status") or "")
        if terminal_status in {"completed", "escalated", "failed"}:
            await self._publish_new_events(values)
            self._persist_terminal_message(values)
            if unresolved is not None:
                decision = str(values.get("approval_decision") or "")
                if decision in {"approve", "reject"}:
                    status = "approved" if decision == "approve" else "rejected"
                    checkpoint_id = str(unresolved["checkpoint_id"])
                    self._interrupt_repository.complete_resolution(
                        checkpoint_id=checkpoint_id,
                        status=status,
                    )
                    self._workflow_run_repository.add_pending_approval(
                        thread_id,
                        {"checkpoint_id": checkpoint_id},
                    )
                    self._workflow_run_repository.resolve_approval(
                        thread_id=thread_id,
                        checkpoint_id=checkpoint_id,
                        decision=decision,
                        comment=(
                            str(values["comments"]) if values.get("comments") is not None else None
                        ),
                        reviewer=(
                            str(values["reviewer"]) if values.get("reviewer") is not None else None
                        ),
                    )
            self._workflow_run_repository.update_workflow_status(thread_id, terminal_status)
            return ReconciliationResult(
                thread_id=thread_id,
                graph_status=terminal_status,
                repaired=unresolved is not None,
            )

        if unresolved is not None and not self._snapshot_exists(snapshot):
            orphaned_ids = self._interrupt_repository.mark_thread_orphaned(
                thread_id=thread_id,
                reason="authoritative_graph_checkpoint_missing",
            )
            for orphaned_id in orphaned_ids:
                self._workflow_run_repository.remove_approval_projection(orphaned_id)
            await self._publish_reconciliation_failure(
                thread_id,
                "authoritative_graph_checkpoint_missing",
            )
            return ReconciliationResult(
                thread_id=thread_id,
                graph_status="orphaned",
                repaired=bool(orphaned_ids),
            )

        await self._publish_new_events(values)
        return ReconciliationResult(
            thread_id=thread_id,
            graph_status="running" if self._snapshot_exists(snapshot) else "absent",
        )

    async def _invoke(
        self,
        graph_input: OrderResolutionState | Command,
        *,
        thread_id: str,
    ) -> dict[str, Any]:
        graph = await self._get_graph()
        config = {"configurable": {"thread_id": thread_id}}
        await graph.ainvoke(graph_input, config=config)
        await self.reconcile_thread(thread_id)
        snapshot = await graph.aget_state(config)
        return dict(snapshot.values or {})

    async def _get_graph(self) -> Any:
        if self._graph is not None:
            return self._graph
        async with self._graph_lock:
            if self._graph is None:
                checkpointer = await self._checkpointer_factory.get()
                self._graph = build_order_resolution_graph(
                    self._node_dependencies,
                    checkpointer=checkpointer,
                )
            return self._graph

    async def _authoritative_interrupt(self, thread_id: str) -> tuple[Any, dict[str, str] | None]:
        graph = await self._get_graph()
        snapshot = await graph.aget_state({"configurable": {"thread_id": thread_id}})
        return snapshot, self._interrupt_from_snapshot(snapshot, dict(snapshot.values or {}))

    @staticmethod
    def _interrupt_from_snapshot(
        snapshot: Any,
        values: dict[str, Any],
    ) -> dict[str, str] | None:
        interrupts = [item for task in snapshot.tasks for item in getattr(task, "interrupts", ())]
        if len(interrupts) > 1:
            raise RuntimeError(
                "Order resolution supports only one unresolved interrupt per thread."
            )
        if not interrupts:
            return None
        checkpoint_id = values.get("approval_checkpoint_id")
        if not isinstance(checkpoint_id, str) or not checkpoint_id:
            raise RuntimeError(
                "Interrupted graph state is missing its opaque approval checkpoint ID."
            )
        configurable = snapshot.config.get("configurable", {})
        return {
            "checkpoint_id": checkpoint_id,
            "langgraph_checkpoint_id": str(configurable.get("checkpoint_id") or ""),
            "langgraph_checkpoint_ns": str(configurable.get("checkpoint_ns") or ""),
            "interrupt_id": str(getattr(interrupts[0], "id", "") or ""),
        }

    @staticmethod
    def _validate_resume_projection(
        *,
        checkpoint_id: str,
        mapping: dict[str, Any],
        interrupt_info: dict[str, str] | None,
    ) -> None:
        if interrupt_info is None:
            raise ValueError(f"Thread has no unresolved LangGraph interrupt for {checkpoint_id}.")
        expected = {
            "checkpoint_id": checkpoint_id,
            "langgraph_checkpoint_id": interrupt_info["langgraph_checkpoint_id"],
            "langgraph_checkpoint_ns": interrupt_info["langgraph_checkpoint_ns"],
            "interrupt_id": interrupt_info["interrupt_id"],
        }
        for key, value in expected.items():
            if str(mapping.get(key) or "") != value:
                raise RuntimeError(f"Approval projection is inconsistent with graph state: {key}.")

    @staticmethod
    def _validate_approval_business_state(values: dict[str, Any]) -> None:
        order = values.get("order")
        if (
            not isinstance(order, dict)
            or not isinstance(order.get("order_id"), str)
            or not order["order_id"]
        ):
            raise RuntimeError("Authoritative graph state is missing the approval order.")
        if not isinstance(values.get("action"), str) or not values["action"]:
            raise RuntimeError("Authoritative graph state is missing the approval action.")
        if not isinstance(values.get("amount"), int | float):
            raise RuntimeError("Authoritative graph state is missing the approval amount.")

    @staticmethod
    def _snapshot_exists(snapshot: Any) -> bool:
        configurable = snapshot.config.get("configurable", {})
        return bool(snapshot.values) or bool(configurable.get("checkpoint_id"))

    async def _publish_new_events(self, result: dict[str, Any]) -> None:
        for raw_event in result.get("events", []):
            event = WorkflowEvent.model_validate(raw_event)
            if self._workflow_run_repository.workflow_event_exists(event.id):
                continue
            await self._event_bus.publish(event)

    def _persist_terminal_message(self, result: dict[str, Any]) -> None:
        output = result.get("output")
        if not isinstance(output, dict):
            return
        message = output.get("message")
        if not isinstance(message, str) or not message:
            return
        self._memory_store.append_message(
            str(result["thread_id"]),
            "assistant",
            message,
            dedupe_key=f"{result['run_id']}:assistant",
        )

    async def _publish_reconciliation_failure(
        self,
        thread_id: str,
        reason: str,
    ) -> None:
        event = WorkflowEvent(
            id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"order-resolution:{thread_id}:reconciliation-failed",
                )
            ),
            type="workflow.failed",
            thread_id=thread_id,
            payload={
                "status": "failed",
                "code": "CheckpointReconciliationError",
                "message": "The saved workflow approval could not be recovered.",
                "reconciliation_reason": reason,
            },
        )
        if not self._workflow_run_repository.workflow_event_exists(event.id):
            await self._event_bus.publish(event)

    async def _publish_failure(self, context: WorkflowContext, exc: Exception) -> None:
        event = WorkflowEvent(
            id=str(
                uuid5(
                    NAMESPACE_URL,
                    f"order-resolution:{context.run_id}:workflow.failed",
                )
            ),
            type="workflow.failed",
            thread_id=context.thread_id,
            payload={
                "status": "failed",
                "code": exc.__class__.__name__,
                "message": str(exc),
                "workflow_run_id": context.run_id,
                "session_id": context.session_id,
            },
        )
        if not self._workflow_run_repository.workflow_event_exists(event.id):
            await self._event_bus.publish(event)
