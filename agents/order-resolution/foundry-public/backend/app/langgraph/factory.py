from __future__ import annotations

from typing import Any

from app.langgraph.nodes import NodeDependencies, OrderResolutionNodes
from app.langgraph.state import OrderResolutionState

from langgraph.graph import END, START, StateGraph


def build_order_resolution_graph(
    dependencies: NodeDependencies,
    *,
    checkpointer: Any,
):
    nodes = OrderResolutionNodes(dependencies)
    builder = StateGraph(OrderResolutionState)
    builder.add_node("classify_request", nodes.classify_request)
    builder.add_node("explanation", nodes.explain)
    builder.add_node("triage", nodes.triage)
    builder.add_node("policy_retrieval", nodes.retrieve_policy)
    builder.add_node("resolution", nodes.resolve)
    builder.add_node("approval_prepare", nodes.prepare_approval)
    builder.add_node("approval_interrupt", nodes.request_approval)
    builder.add_node("submission", nodes.submit)
    builder.add_node("rejection_escalation", nodes.reject)
    builder.add_node("terminal_output", nodes.terminal)

    builder.add_edge(START, "classify_request")
    builder.add_conditional_edges(
        "classify_request",
        nodes.route_request,
        {"explanation": "explanation", "resolution": "triage"},
    )
    builder.add_edge("explanation", "terminal_output")
    builder.add_edge("triage", "policy_retrieval")
    builder.add_edge("policy_retrieval", "resolution")
    builder.add_conditional_edges(
        "resolution",
        nodes.route_resolution,
        {"approval": "approval_prepare", "submit": "submission"},
    )
    builder.add_edge("approval_prepare", "approval_interrupt")
    builder.add_conditional_edges(
        "approval_interrupt",
        nodes.route_approval,
        {"submit": "submission", "reject": "rejection_escalation"},
    )
    builder.add_edge("submission", "terminal_output")
    builder.add_edge("rejection_escalation", "terminal_output")
    builder.add_edge("terminal_output", END)
    return builder.compile(
        checkpointer=checkpointer,
        name="order_resolution",
    )
