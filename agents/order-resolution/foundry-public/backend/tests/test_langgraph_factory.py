from __future__ import annotations

from app.infrastructure.mcp import MCPKnowledgeTool
from app.infrastructure.persistence import IdempotencyStore
from app.infrastructure.rag.providers.noop_provider import NoopRAGProvider
from app.langgraph.clients import AzureTriageModel
from app.langgraph.factory import build_order_resolution_graph
from app.langgraph.nodes import NodeDependencies
from langgraph.checkpoint.memory import InMemorySaver


def test_graph_factory_builds_single_typed_state_graph() -> None:
    graph = build_order_resolution_graph(
        NodeDependencies(
            triage_model=AzureTriageModel(),
            rag_provider=NoopRAGProvider(),
            mcp_tool=MCPKnowledgeTool(endpoint=None),
            idempotency_store=IdempotencyStore(),
        ),
        checkpointer=InMemorySaver(),
    )

    nodes = set(graph.get_graph().nodes)
    assert {
        "classify_request",
        "explanation",
        "triage",
        "policy_retrieval",
        "resolution",
        "approval_prepare",
        "approval_interrupt",
        "submission",
        "rejection_escalation",
        "terminal_output",
    } <= nodes
