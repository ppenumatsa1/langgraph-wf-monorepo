from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.langgraph.nodes import NodeDependencies, UnderwritingNodes
from app.langgraph.state import UnderwritingState

GRAPH_NAME = "insurance-underwriting-langgraph"


def build_underwriting_graph(
    dependencies: NodeDependencies,
    *,
    checkpointer: Any,
):
    nodes = UnderwritingNodes(dependencies)
    builder = StateGraph(UnderwritingState)
    builder.add_node("init_context", nodes.init_context)
    builder.add_node("risk_score", nodes.risk_score)
    builder.add_node("credit_check", nodes.credit_check)
    builder.add_node("medical_check", nodes.medical_check)
    builder.add_node("driving_check", nodes.driving_check)
    builder.add_node("fan_in_aggregator", nodes.fan_in_aggregator)
    builder.add_node("final_decision", nodes.final_decision)

    builder.add_edge(START, "init_context")
    builder.add_edge("init_context", "risk_score")
    builder.add_edge("init_context", "credit_check")
    builder.add_edge("init_context", "medical_check")
    builder.add_edge("init_context", "driving_check")
    builder.add_edge("risk_score", "fan_in_aggregator")
    builder.add_edge("credit_check", "fan_in_aggregator")
    builder.add_edge("medical_check", "fan_in_aggregator")
    builder.add_edge("driving_check", "fan_in_aggregator")
    builder.add_edge("fan_in_aggregator", "final_decision")
    builder.add_edge("final_decision", END)

    return builder.compile(checkpointer=checkpointer, name=GRAPH_NAME)
