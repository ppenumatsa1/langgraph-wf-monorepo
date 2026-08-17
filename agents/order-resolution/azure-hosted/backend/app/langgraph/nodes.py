from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from uuid import NAMESPACE_URL, uuid4, uuid5

from app.core.telemetry import record_business_event, workflow_stage_span
from app.infrastructure.rag import RAGProvider, RetrievalRequest, RetrievalResult
from app.langgraph.clients import TriageModel, triage_mode_metadata
from app.langgraph.state import OrderResolutionState
from app.langgraph.tools import (
    deterministic_inputs,
    deterministic_triage_summary,
    submit_resolution,
)
from app.modules.order_resolution.hitl import requires_hitl, resolve_action
from app.modules.order_resolution.models import WorkflowEvent
from app.modules.order_resolution.ports import IdempotencyRepository, McpKnowledgePort

from langgraph.types import interrupt


@dataclass(frozen=True)
class NodeDependencies:
    triage_model: TriageModel
    rag_provider: RAGProvider
    mcp_tool: McpKnowledgePort
    idempotency_store: IdempotencyRepository
    retry_attempts: int = 3
    retry_delay_seconds: float = 0.2


class OrderResolutionNodes:
    def __init__(self, dependencies: NodeDependencies) -> None:
        self._dependencies = dependencies

    async def classify_request(self, state: OrderResolutionState) -> dict[str, Any]:
        request_kind = (
            "explanation"
            if "why" in state["user_message"].lower()
            and "resolution" in state["user_message"].lower()
            else "resolution"
        )
        return {"request_kind": request_kind}

    async def explain(self, state: OrderResolutionState) -> dict[str, Any]:
        with self._span("explanation", state):
            prior_user = self._prior_message(state, "user")
            if not prior_user:
                message = "I could not find a prior user request to explain."
            else:
                issue_type, order, policy = deterministic_inputs(prior_user)
                action = resolve_action(issue_type)
                needs_approval = requires_hitl(issue_type, order.total_amount, policy)
                hitl_factor = (
                    "HITL approval was required."
                    if needs_approval
                    else "HITL approval was not required."
                )
                message = (
                    f"The prior request was for order {order.order_id}: issue "
                    f"{issue_type}, status {order.state}, policy {policy}, action "
                    f"{action}, and amount ${order.total_amount:.2f}. {hitl_factor}"
                )
                prior_assistant = self._prior_message(state, "assistant")
                if prior_assistant:
                    message = f"{message} Previous result: {prior_assistant}"
            output = {"message": message, "status": "completed"}
            return {
                "output": output,
                "terminal_status": "completed",
                "events": [
                    self._event(
                        state,
                        "workflow.stage",
                        {"agent": "explanation", "status": "completed"},
                        "explanation.completed",
                    ),
                    self._event(state, "workflow.output", output, "workflow.output"),
                ],
            }

    async def triage(self, state: OrderResolutionState) -> dict[str, Any]:
        with self._span("triage", state):
            configured_mode = triage_mode_metadata()
            used_model = False
            try:
                summary, used_model = await self._retry(
                    lambda: self._dependencies.triage_model.summarize(
                        message=state["user_message"],
                        context_summary=self._context_summary(state),
                    )
                )
            except Exception as exc:
                summary = f"triage_summary: {deterministic_triage_summary(state['user_message'])}"
                configured_mode = {
                    "provider": "deterministic",
                    "mode": "model_error_fallback",
                    "error_type": exc.__class__.__name__,
                }
            mode = configured_mode
            if used_model:
                mode = triage_mode_metadata()
            return {
                "triage_summary": summary,
                "triage_mode": mode,
                "events": [
                    self._event(
                        state,
                        "workflow.stage",
                        {
                            "agent": "triage",
                            "status": "started",
                            "triage_mode": configured_mode,
                        },
                        "triage.started",
                    ),
                    self._event(
                        state,
                        "workflow.stage",
                        {
                            "agent": "triage",
                            "status": "completed",
                            "result": {"summary": summary},
                            "triage_mode": mode,
                        },
                        "triage.completed",
                    ),
                ],
            }

    async def retrieve_policy(self, state: OrderResolutionState) -> dict[str, Any]:
        with self._span("policy_retrieval", state):
            issue_type, order, policy = deterministic_inputs(state["user_message"])
            try:
                rag_result = await self._retry(
                    lambda: self._dependencies.rag_provider.retrieve(
                        RetrievalRequest(
                            thread_id=state["thread_id"],
                            query=f"Policy guidance for {issue_type}",
                            issue_type=issue_type,
                            top_k=3,
                        )
                    )
                )
            except Exception:
                rag_result = RetrievalResult(
                    provider="rag-fallback",
                    query_id=str(uuid4()),
                    evidence=[],
                )
            mcp_result = await self._retry(
                lambda: self._dependencies.mcp_tool.search(f"Policy guidance for {issue_type}")
            )
            serialized_rag = {
                "provider": rag_result.provider,
                "query_id": rag_result.query_id,
                "evidence": [
                    {
                        "evidence_id": item.evidence_id,
                        "document_id": item.document_id,
                        "content": item.content,
                        "score": item.score,
                        "metadata": item.metadata,
                    }
                    for item in rag_result.evidence
                ],
            }
            return {
                "issue_type": issue_type,
                "order": order.to_dict(),
                "policy": policy,
                "rag_result": serialized_rag,
                "mcp_result": mcp_result,
                "events": [
                    self._event(
                        state,
                        "workflow.stage",
                        {"agent": "policy_retrieval", "status": "started"},
                        "policy.started",
                    ),
                    self._event(
                        state,
                        "workflow.stage",
                        {
                            "agent": "policy_retrieval",
                            "status": "completed",
                            "result": {
                                "provider": rag_result.provider,
                                "query_id": rag_result.query_id,
                                "count": len(rag_result.evidence),
                            },
                        },
                        "policy.completed",
                    ),
                    self._event(
                        state,
                        "tool.call",
                        {
                            "local_tool": "fetch_order_status/fetch_policy",
                            "mcp_tool": "search",
                            "order": order.to_dict(),
                            "policy": policy,
                            "policy_evidence_ids": [
                                item.evidence_id for item in rag_result.evidence
                            ],
                            "policy_retrieval": {
                                "provider": rag_result.provider,
                                "query_id": rag_result.query_id,
                                "count": len(rag_result.evidence),
                            },
                            "mcp_result": mcp_result,
                        },
                        "policy.tools",
                    ),
                ],
            }

    async def resolve(self, state: OrderResolutionState) -> dict[str, Any]:
        with self._span("resolution", state):
            action = resolve_action(state["issue_type"])
            amount = float(state["order"]["total_amount"])
            needs_approval = requires_hitl(state["issue_type"], amount, state["policy"])
            return {
                "action": action,
                "amount": amount,
                "requires_approval": needs_approval,
                "events": [
                    self._event(
                        state,
                        "workflow.stage",
                        {
                            "agent": "resolution",
                            "status": "completed",
                            "result": {
                                "action": action,
                                "requires_hitl": needs_approval,
                                "amount": amount,
                            },
                        },
                        "resolution.completed",
                    )
                ],
            }

    async def prepare_approval(self, state: OrderResolutionState) -> dict[str, Any]:
        with self._span("approval_prepare", state):
            checkpoint_id = state.get("approval_checkpoint_id") or str(
                uuid5(
                    NAMESPACE_URL,
                    f"order-resolution:{state['run_id']}:approval",
                )
            )
            return {
                "approval_checkpoint_id": checkpoint_id,
                "events": [
                    self._event(
                        state,
                        "checkpoint.created",
                        {
                            "checkpoint_id": checkpoint_id,
                            "reason": "approval_required",
                        },
                        "checkpoint.created",
                    ),
                    self._event(
                        state,
                        "hitl.request",
                        {
                            "checkpoint_id": checkpoint_id,
                            "action": state["action"],
                            "order_id": state["order"]["order_id"],
                            "amount": state["amount"],
                            "question": "Approve the proposed action?",
                        },
                        "hitl.request",
                    ),
                ],
            }

    async def request_approval(self, state: OrderResolutionState) -> dict[str, Any]:
        decision_payload = interrupt(
            {
                "checkpoint_id": state["approval_checkpoint_id"],
                "action": state["action"],
                "order_id": state["order"]["order_id"],
                "amount": state["amount"],
                "question": "Approve the proposed action?",
            }
        )
        if not isinstance(decision_payload, dict):
            raise ValueError("Approval resume payload must be an object.")
        decision = str(decision_payload.get("decision", "")).strip().lower()
        if decision not in {"approve", "reject"}:
            raise ValueError("Approval decision must be approve or reject.")
        reviewer = str(decision_payload.get("reviewer") or "unknown")
        comments = decision_payload.get("comments")
        normalized_comments = str(comments) if comments is not None else None
        return {
            "approval_decision": decision,
            "reviewer": reviewer,
            "comments": normalized_comments,
            "events": [
                self._event(
                    state,
                    "hitl.response",
                    {
                        "checkpoint_id": state["approval_checkpoint_id"],
                        "decision": decision,
                        "reviewer": reviewer,
                        "comments": normalized_comments,
                    },
                    "hitl.response",
                )
            ],
        }

    async def submit(self, state: OrderResolutionState) -> dict[str, Any]:
        with self._span("resolution_submit", state):
            order_id = str(state["order"]["order_id"])
            action = state["action"]
            submission_id, replayed = await asyncio.to_thread(
                self._dependencies.idempotency_store.execute_once,
                workflow_run_id=state["run_id"],
                step_name="submit_resolution",
                business_id=order_id,
                operation=lambda: submit_resolution(action=action, order_id=order_id),
            )
            record_business_event(
                "langgraph.resolution.submitted",
                {
                    "workflow.thread_id": state["thread_id"],
                    "workflow.run_id": state["run_id"],
                    "workflow.replayed": replayed,
                },
            )
            output = {
                "message": self._completion_message(action=action, order_id=order_id),
                "submission_id": submission_id,
                "status": "completed",
            }
            return {
                "submission_id": submission_id,
                "output": output,
                "terminal_status": "completed",
                "events": [self._event(state, "workflow.output", output, "workflow.output")],
            }

    async def reject(self, state: OrderResolutionState) -> dict[str, Any]:
        with self._span("rejection_escalation", state):
            output = {
                "message": (
                    "Request rejected by reviewer. Escalating to human support specialist."
                ),
                "status": "escalated",
            }
            return {
                "output": output,
                "terminal_status": "escalated",
                "events": [self._event(state, "workflow.output", output, "workflow.output")],
            }

    async def terminal(self, state: OrderResolutionState) -> dict[str, Any]:
        record_business_event(
            "langgraph.workflow.terminal",
            {
                "workflow.thread_id": state["thread_id"],
                "workflow.run_id": state["run_id"],
                "workflow.status": state.get("terminal_status"),
            },
        )
        return {}

    @staticmethod
    def route_request(state: OrderResolutionState) -> str:
        return state["request_kind"]

    @staticmethod
    def route_resolution(state: OrderResolutionState) -> str:
        return "approval" if state["requires_approval"] else "submit"

    @staticmethod
    def route_approval(state: OrderResolutionState) -> str:
        return "submit" if state.get("approval_decision") == "approve" else "reject"

    async def _retry(self, operation):
        last_error: Exception | None = None
        for attempt in range(1, max(1, self._dependencies.retry_attempts) + 1):
            try:
                return await operation()
            except Exception as exc:
                last_error = exc
                if attempt >= self._dependencies.retry_attempts:
                    break
                await asyncio.sleep(max(0.0, self._dependencies.retry_delay_seconds) * attempt)
        if last_error is not None:
            raise last_error
        raise RuntimeError("Read operation failed without raising an exception.")

    @staticmethod
    def _event(
        state: OrderResolutionState,
        event_type: str,
        payload: dict[str, Any],
        logical_key: str,
    ) -> dict[str, Any]:
        event_id = str(
            uuid5(
                NAMESPACE_URL,
                f"order-resolution:{state['run_id']}:{logical_key}",
            )
        )
        enriched = dict(payload)
        enriched.setdefault("workflow_run_id", state["run_id"])
        enriched.setdefault("session_id", state["session_id"])
        return WorkflowEvent(
            id=event_id,
            type=event_type,
            thread_id=state["thread_id"],
            payload=enriched,
        ).model_dump()

    @staticmethod
    def _prior_message(state: OrderResolutionState, role: str) -> str | None:
        for item in reversed(state.get("conversation_history", [])):
            if str(item.get("role", "")).strip().lower() != role:
                continue
            content = str(item.get("content", "")).strip()
            if content:
                return content
        return None

    @staticmethod
    def _context_summary(state: OrderResolutionState) -> str:
        return "\n".join(
            f"{item.get('role', 'unknown')}: {item.get('content', '')}"
            for item in state.get("conversation_history", [])[-8:]
        )

    @staticmethod
    def _completion_message(*, action: str, order_id: str) -> str:
        if action == "issue_partial_refund":
            return (
                f"Your partial refund has been submitted for order {order_id}. "
                "It will be returned to your original payment method within 5-10 "
                "business days; you will receive a confirmation once processing "
                "is complete."
            )
        return f"Resolution complete. Action '{action}' submitted for order {order_id}."

    @staticmethod
    def _span(stage: str, state: OrderResolutionState):
        return workflow_stage_span(
            f"node.{stage}",
            {
                "workflow.thread_id": state.get("thread_id"),
                "workflow.run_id": state.get("run_id"),
                "workflow.session_id": state.get("session_id"),
                "langgraph.node": stage,
            },
            parent_trace_context=state.get("trace_context"),
        )
