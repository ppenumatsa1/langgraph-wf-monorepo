from __future__ import annotations

import asyncio
import time

import pytest
from app.infrastructure.mcp import MCPKnowledgeTool
from app.infrastructure.rag.providers.noop_provider import NoopRAGProvider
from app.langgraph.nodes import NodeDependencies, OrderResolutionNodes


class _FailingModel:
    async def summarize(self, *, message: str, context_summary: str):
        raise RuntimeError("model unavailable")


class _InMemoryIdempotency:
    def __init__(self) -> None:
        self.results: dict[str, str] = {}

    def execute_once(
        self,
        *,
        workflow_run_id: str,
        step_name: str,
        business_id: str,
        operation,
    ):
        key = f"{workflow_run_id}:{step_name}:{business_id}"
        if key in self.results:
            return self.results[key], True
        self.results[key] = operation()
        return self.results[key], False


class _BlockingIdempotency:
    def __init__(self, delay_seconds: float) -> None:
        self.delay_seconds = delay_seconds

    def execute_once(
        self,
        *,
        workflow_run_id: str,
        step_name: str,
        business_id: str,
        operation,
    ):
        time.sleep(self.delay_seconds)
        return operation(), False


def _state(message: str) -> dict:
    return {
        "run_id": "run-1",
        "thread_id": "thread-1",
        "session_id": "session-1",
        "customer_id": "customer-1",
        "user_message": message,
        "conversation_history": [],
        "trace_context": None,
        "events": [],
    }


def _nodes() -> OrderResolutionNodes:
    return OrderResolutionNodes(
        NodeDependencies(
            triage_model=_FailingModel(),
            rag_provider=NoopRAGProvider(),
            mcp_tool=MCPKnowledgeTool(endpoint=None),
            idempotency_store=_InMemoryIdempotency(),
            retry_attempts=1,
            retry_delay_seconds=0,
        )
    )


@pytest.mark.asyncio
async def test_triage_model_failure_falls_back_inside_graph_node() -> None:
    result = await _nodes().triage(_state("Order ORD-1009 is late."))

    assert result["triage_summary"].endswith("order_id=ord-1009; issue_type=late_delivery")
    assert result["triage_mode"]["mode"] == "model_error_fallback"
    assert [event["type"] for event in result["events"]] == [
        "workflow.stage",
        "workflow.stage",
    ]


@pytest.mark.asyncio
async def test_resolution_rules_remain_deterministic() -> None:
    state = _state("Order ORD-1004 arrived damaged.")
    state.update(
        {
            "issue_type": "damaged_item",
            "order": {
                "order_id": "ord-1001",
                "state": "in_transit",
                "total_amount": 79.0,
            },
            "policy": "replacement_or_full_refund_with_photo_proof",
        }
    )

    result = await _nodes().resolve(state)

    assert result["action"] == "offer_replacement_or_full_refund"
    assert result["requires_approval"] is True


@pytest.mark.asyncio
async def test_approval_preparation_is_idempotent_and_owns_request_events() -> None:
    state = _state("Order ORD-1009 is late.")
    state.update(
        {
            "action": "issue_partial_refund",
            "amount": 185.0,
            "order": {
                "order_id": "ord-1009",
                "state": "delayed",
                "total_amount": 185.0,
            },
        }
    )

    first = await _nodes().prepare_approval(state)
    second = await _nodes().prepare_approval(state)

    assert first["approval_checkpoint_id"] == second["approval_checkpoint_id"]
    assert [event["id"] for event in first["events"]] == [event["id"] for event in second["events"]]
    assert [event["type"] for event in first["events"]] == [
        "checkpoint.created",
        "hitl.request",
    ]


@pytest.mark.asyncio
async def test_submit_keeps_event_loop_responsive_during_idempotency_write() -> None:
    nodes = OrderResolutionNodes(
        NodeDependencies(
            triage_model=_FailingModel(),
            rag_provider=NoopRAGProvider(),
            mcp_tool=MCPKnowledgeTool(endpoint=None),
            idempotency_store=_BlockingIdempotency(0.2),
            retry_attempts=1,
            retry_delay_seconds=0,
        )
    )
    state = _state("Order ORD-1001 arrived late.")
    state.update(
        {
            "action": "issue_partial_refund",
            "order": {
                "order_id": "ord-1001",
                "state": "in_transit",
                "total_amount": 79.0,
            },
        }
    )
    samples: list[float] = []
    stop = asyncio.Event()

    async def ticker() -> None:
        while not stop.is_set():
            samples.append(time.perf_counter())
            await asyncio.sleep(0.01)

    ticker_task = asyncio.create_task(ticker())
    await asyncio.sleep(0)
    await nodes.submit(state)
    await asyncio.sleep(0.02)
    stop.set()
    await ticker_task

    gaps = [later - earlier for earlier, later in zip(samples, samples[1:], strict=False)]
    assert gaps
    assert max(gaps) < 0.1
