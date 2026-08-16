from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.core.database import postgres_db
from app.infrastructure.events import EventBus
from app.infrastructure.mcp import MCPKnowledgeTool
from app.infrastructure.persistence import (
    CheckpointStore,
    IdempotencyStore,
    WorkflowRunRepository,
)
from app.infrastructure.persistence.session_memory import PostgresSessionMemoryStore
from app.infrastructure.rag.providers.noop_provider import NoopRAGProvider
from app.langgraph import (
    AzureTriageModel,
    LangGraphOrderResolutionWorkflow,
    PostgresCheckpointerFactory,
)
from app.langgraph.nodes import NodeDependencies
from app.modules.order_resolution.hitl import classify_issue
from app.modules.order_resolution.models import WorkflowContext
from app.modules.order_resolution.projections import WorkflowRunEventProjector

EXPECTED_EVENT_TYPES = {
    "workflow.stage",
    "tool.call",
    "checkpoint.created",
    "hitl.request",
    "hitl.response",
    "workflow.output",
    "workflow.failed",
}

EXPECTED_HITL_DECISIONS = {"approve", "reject"}

EXPECTED_STAGE_SEQUENCE = [
    "triage:started",
    "triage:completed",
    "policy_retrieval:started",
    "policy_retrieval:completed",
    "resolution:completed",
]


@dataclass(frozen=True)
class EvalCase:
    id: str
    input: str
    expect_hitl: bool
    expected_order_id: str | None = None
    expected_issue_type: str | None = None
    expected_policy: str | None = None
    expected_action: str | None = None
    expected_amount: float | None = None
    expected_terminal_status: str | None = None
    expected_event_sequence: tuple[str, ...] = ()
    follow_up: str | None = None
    hitl_decision: str | None = None
    assert_duplicate_hitl_response: bool = False
    requires_explanation: bool = False
    expected_explanation_factors: tuple[str, ...] = ()
    prohibited_claims: tuple[str, ...] = ()


def _load_cases(cases_path: Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    for index, line in enumerate(cases_path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if "id" not in row or "input" not in row or "expect_hitl" not in row:
            raise ValueError(f"{cases_path}:{index} missing required keys (id,input,expect_hitl)")
        if not isinstance(row["id"], str) or not row["id"].strip():
            raise ValueError(f"{cases_path}:{index} invalid id")
        if not isinstance(row["input"], str) or not row["input"].strip():
            raise ValueError(f"{cases_path}:{index} invalid input")
        if not isinstance(row["expect_hitl"], bool):
            raise ValueError(f"{cases_path}:{index} expect_hitl must be boolean")
        hitl_decision = row.get("hitl_decision")
        if hitl_decision is not None and hitl_decision not in EXPECTED_HITL_DECISIONS:
            raise ValueError(
                f"{cases_path}:{index} invalid hitl_decision '{hitl_decision}', expected approve/reject"
            )
        expected_event_sequence = row.get("expected_event_sequence", [])
        if not isinstance(expected_event_sequence, list) or not all(
            isinstance(event_type, str) and event_type in EXPECTED_EVENT_TYPES
            for event_type in expected_event_sequence
        ):
            raise ValueError(
                f"{cases_path}:{index} expected_event_sequence must be a list of known event types"
            )
        prohibited_claims = row.get("prohibited_claims", [])
        if not isinstance(prohibited_claims, list) or not all(
            isinstance(claim, str) and claim for claim in prohibited_claims
        ):
            raise ValueError(
                f"{cases_path}:{index} prohibited_claims must be a list of non-empty strings"
            )
        explanation_factors = row.get("expected_explanation_factors", [])
        if not isinstance(explanation_factors, list) or not all(
            isinstance(factor, str) and factor for factor in explanation_factors
        ):
            raise ValueError(
                f"{cases_path}:{index} expected_explanation_factors must be a list of non-empty strings"
            )

        cases.append(
            EvalCase(
                id=row["id"].strip(),
                input=row["input"].strip(),
                expect_hitl=row["expect_hitl"],
                expected_order_id=row.get("expected_order_id"),
                expected_issue_type=row.get("expected_issue_type"),
                expected_policy=row.get("expected_policy"),
                expected_action=row.get("expected_action"),
                expected_amount=float(row["expected_amount"])
                if row.get("expected_amount") is not None
                else None,
                expected_terminal_status=row.get("expected_terminal_status"),
                expected_event_sequence=tuple(expected_event_sequence),
                follow_up=row.get("follow_up"),
                hitl_decision=hitl_decision,
                assert_duplicate_hitl_response=bool(
                    row.get("assert_duplicate_hitl_response", False)
                ),
                requires_explanation=bool(row.get("requires_explanation", False)),
                expected_explanation_factors=tuple(explanation_factors),
                prohibited_claims=tuple(prohibited_claims),
            )
        )
    return cases


def _event_types(history: Sequence[dict[str, object]]) -> list[str]:
    return [str(event.get("type")) for event in history]


def _assert_event_sequence(history: Sequence[dict[str, object]], expected: Sequence[str]) -> None:
    event_types = _event_types(history)
    cursor = 0
    for expected_type in expected:
        try:
            idx = event_types.index(expected_type, cursor)
        except ValueError as exc:
            raise AssertionError(
                f"missing expected event '{expected_type}' in sequence {event_types}"
            ) from exc
        cursor = idx + 1


def _extract_stage_sequence(history: Sequence[dict[str, object]]) -> list[str]:
    stage_sequence: list[str] = []
    for event in history:
        if event.get("type") != "workflow.stage":
            continue
        payload = event.get("payload")
        if not isinstance(payload, dict):
            continue
        agent = str(payload.get("agent", "")).strip()
        status = str(payload.get("status", "")).strip()
        if not agent or not status:
            continue
        stage_sequence.append(f"{agent}:{status}")
    return stage_sequence


def _history_for_thread(event_bus: EventBus, thread_id: str) -> list[dict[str, object]]:
    return json.loads(event_bus.history_as_json(thread_id))


def _last_output_payload(history: Sequence[dict[str, object]]) -> dict[str, object]:
    outputs = [event for event in history if event.get("type") == "workflow.output"]
    if not outputs:
        raise AssertionError("workflow.output missing")
    payload = outputs[-1].get("payload")
    if not isinstance(payload, dict):
        raise AssertionError("workflow.output payload missing")
    return payload


def _assert_claims_absent(message: str, prohibited_claims: Sequence[str]) -> None:
    lower_message = message.lower()
    for claim in prohibited_claims:
        if claim.lower() in lower_message:
            raise AssertionError(f"prohibited claim detected: '{claim}'")


async def _run_case(*, case: EvalCase, workflow, event_bus: EventBus) -> dict[str, object]:
    thread_id = str(uuid4())
    context = WorkflowContext(
        run_id=str(uuid4()),
        thread_id=thread_id,
        session_id=thread_id,
        customer_id="eval-user",
        user_message=case.input,
    )
    await workflow.start(context)

    history = _history_for_thread(event_bus, thread_id)
    stage_sequence = _extract_stage_sequence(history)
    if stage_sequence[: len(EXPECTED_STAGE_SEQUENCE)] != EXPECTED_STAGE_SEQUENCE:
        raise AssertionError(f"unexpected stage sequence: {stage_sequence}")

    has_hitl = "hitl.request" in _event_types(history)
    if has_hitl != case.expect_hitl:
        raise AssertionError(
            f"HITL expectation mismatch: expected={case.expect_hitl} actual={has_hitl}"
        )

    tool_event = next((event for event in history if event.get("type") == "tool.call"), None)
    if not isinstance(tool_event, dict):
        raise AssertionError("tool.call event missing")
    tool_payload = tool_event.get("payload")
    if not isinstance(tool_payload, dict):
        raise AssertionError("tool.call payload missing")

    resolution_stage = next(
        (
            event
            for event in history
            if event.get("type") == "workflow.stage"
            and isinstance(event.get("payload"), dict)
            and event["payload"].get("agent") == "resolution"
            and event["payload"].get("status") == "completed"
        ),
        None,
    )
    if not isinstance(resolution_stage, dict):
        raise AssertionError("resolution stage completed event missing")
    resolution_result = resolution_stage["payload"].get("result")
    if not isinstance(resolution_result, dict):
        raise AssertionError("resolution stage result missing")

    if case.expected_issue_type and classify_issue(case.input.lower()) != case.expected_issue_type:
        raise AssertionError(
            f"issue_type mismatch: expected={case.expected_issue_type}, "
            f"actual={classify_issue(case.input.lower())}"
        )

    if case.expected_order_id:
        order_payload = tool_payload.get("order")
        if not isinstance(order_payload, dict):
            raise AssertionError("tool.call payload missing order details")
        actual_order_id = str(order_payload.get("order_id", ""))
        if actual_order_id != case.expected_order_id:
            raise AssertionError(
                f"order_id mismatch: expected={case.expected_order_id}, actual={actual_order_id}"
            )

    if case.expected_policy:
        actual_policy = str(tool_payload.get("policy", ""))
        if actual_policy != case.expected_policy:
            raise AssertionError(
                f"policy mismatch: expected={case.expected_policy}, actual={actual_policy}"
            )

    if case.expected_amount is not None:
        order_payload = tool_payload.get("order")
        if not isinstance(order_payload, dict):
            raise AssertionError("tool.call payload missing order amount")
        actual_amount = float(order_payload.get("total_amount", 0.0))
        if actual_amount != case.expected_amount:
            raise AssertionError(
                f"amount mismatch: expected={case.expected_amount}, actual={actual_amount}"
            )

    if case.expected_action:
        actual_action = str(resolution_result.get("action", ""))
        if actual_action != case.expected_action:
            raise AssertionError(
                f"action mismatch: expected={case.expected_action}, actual={actual_action}"
            )

    if has_hitl and case.hitl_decision:
        checkpoint_event = next(
            (event for event in history if event.get("type") == "checkpoint.created"), None
        )
        if not isinstance(checkpoint_event, dict):
            raise AssertionError("checkpoint.created missing for HITL case")
        checkpoint_payload = checkpoint_event.get("payload")
        if not isinstance(checkpoint_payload, dict):
            raise AssertionError("checkpoint payload missing")
        checkpoint_id = str(checkpoint_payload.get("checkpoint_id", ""))
        if not checkpoint_id:
            raise AssertionError("checkpoint_id missing")

        await workflow.handle_hitl_response(
            checkpoint_id=checkpoint_id,
            decision=case.hitl_decision,
            reviewer="eval-bot",
            comments=f"deterministic-{case.hitl_decision}",
        )
        history = _history_for_thread(event_bus, thread_id)

        if case.assert_duplicate_hitl_response:
            before_len = len(history)
            before_hitl_responses = sum(
                1 for event in history if event.get("type") == "hitl.response"
            )
            before_outputs = sum(1 for event in history if event.get("type") == "workflow.output")
            await workflow.handle_hitl_response(
                checkpoint_id=checkpoint_id,
                decision=case.hitl_decision,
                reviewer="eval-bot",
                comments="duplicate-decision",
            )
            history = _history_for_thread(event_bus, thread_id)
            after_hitl_responses = sum(
                1 for event in history if event.get("type") == "hitl.response"
            )
            after_outputs = sum(1 for event in history if event.get("type") == "workflow.output")
            if len(history) != before_len:
                raise AssertionError("duplicate HITL response produced additional events")
            if after_hitl_responses != before_hitl_responses:
                raise AssertionError("duplicate HITL response emitted extra hitl.response event")
            if after_outputs != before_outputs:
                raise AssertionError("duplicate HITL response emitted extra workflow.output event")

    if case.follow_up:
        follow_up_context = WorkflowContext(
            run_id=str(uuid4()),
            thread_id=thread_id,
            session_id=thread_id,
            customer_id="eval-user",
            user_message=case.follow_up,
        )
        await workflow.start(follow_up_context)
        history = _history_for_thread(event_bus, thread_id)

    if case.expected_event_sequence:
        _assert_event_sequence(history, case.expected_event_sequence)

    output_payload = _last_output_payload(history)
    output_message = str(output_payload.get("message", ""))

    if case.expected_terminal_status:
        actual_status = str(output_payload.get("status", ""))
        if actual_status != case.expected_terminal_status:
            raise AssertionError(
                f"terminal status mismatch: expected={case.expected_terminal_status}, actual={actual_status}"
            )

    if case.prohibited_claims:
        _assert_claims_absent(output_message, case.prohibited_claims)

    if case.requires_explanation:
        explanation_stage = next(
            (
                event
                for event in history
                if event.get("type") == "workflow.stage"
                and isinstance(event.get("payload"), dict)
                and event["payload"].get("agent") == "explanation"
                and event["payload"].get("status") == "completed"
            ),
            None,
        )
        if explanation_stage is None:
            raise AssertionError("explanation follow-up stage missing")
        for factor in case.expected_explanation_factors:
            if factor.lower() not in output_message.lower():
                raise AssertionError(f"explanation output missing factor: '{factor}'")

    return {
        "id": case.id,
        "thread_id": thread_id,
        "actual_hitl": has_hitl,
        "event_types": _event_types(history),
        "stage_sequence": _extract_stage_sequence(history),
        "last_output": output_payload,
    }


async def run_eval() -> None:
    root = Path(__file__).resolve().parents[1]
    foundry_root = root / ".foundry"
    cases_path = foundry_root / "datasets" / "order-resolution-hosted-cases.jsonl"
    report_path = foundry_root / "results" / "report.json"
    capture_path = foundry_root / "results" / "contract_capture.json"

    event_bus = EventBus()
    workflow_run_repository = WorkflowRunRepository()
    memory_store = PostgresSessionMemoryStore()
    checkpoint_store = CheckpointStore()
    rag_provider = NoopRAGProvider()
    event_bus.add_listener(WorkflowRunEventProjector(workflow_run_repository).sync_event_to_run)
    workflow = LangGraphOrderResolutionWorkflow(
        event_bus=event_bus,
        memory_store=memory_store,
        interrupt_repository=checkpoint_store,
        workflow_run_repository=workflow_run_repository,
        checkpointer_factory=PostgresCheckpointerFactory(postgres_db.database_url),
        node_dependencies=NodeDependencies(
            triage_model=AzureTriageModel(),
            rag_provider=rag_provider,
            mcp_tool=MCPKnowledgeTool(endpoint=None),
            idempotency_store=IdempotencyStore(),
        ),
    )

    cases = _load_cases(cases_path)
    results: list[dict[str, object]] = []
    captures: list[dict[str, object]] = []
    passed = 0

    for case in cases:
        try:
            capture = await _run_case(case=case, workflow=workflow, event_bus=event_bus)
            captures.append(capture)
            results.append(
                {
                    "id": case.id,
                    "expect_hitl": case.expect_hitl,
                    "actual_hitl": capture["actual_hitl"],
                    "passed": True,
                }
            )
            passed += 1
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "id": case.id,
                    "expect_hitl": case.expect_hitl,
                    "passed": False,
                    "error": str(exc),
                }
            )

    total = len(cases)
    report = {
        "runtime": "langgraph",
        "graph": "order_resolution",
        "checkpointer": "async_postgres",
        "strict_msgpack": True,
        "interrupt_reconciliation": "graph_authoritative",
        "max_unresolved_interrupts_per_thread": 1,
        "dataset": str(cases_path.relative_to(root)),
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": 0 if total == 0 else round((passed / total) * 100, 2),
        "results": results,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    capture_path.write_text(
        json.dumps({"total": len(captures), "captures": captures}, indent=2),
        encoding="utf-8",
    )
    await workflow.shutdown()
    print(json.dumps(report, indent=2))
    print(f"Deterministic report saved to: {report_path}")
    print(f"Capture saved to: {capture_path}")
    if passed != total:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(run_eval())
