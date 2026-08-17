from langgraph.checkpoint.memory import InMemorySaver

from app.core.config import load_settings
from app.infrastructure.persistence.idempotency_store import IdempotencyStore
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository
from app.langgraph.factory import GRAPH_NAME, build_underwriting_graph
from app.langgraph.nodes import NodeDependencies
from app.modules.underwriting.decisions import compute_decision


def test_underwriting_langgraph_uses_parallel_check_nodes_and_fan_in() -> None:
    graph = build_underwriting_graph(
        NodeDependencies(
            repository=WorkflowRunRepository(),
            idempotency_store=IdempotencyStore(),
            settings=load_settings(),
            llm_client=None,
        ),
        checkpointer=InMemorySaver(),
    )

    assert graph.name == GRAPH_NAME
    assert {
        "__start__",
        "init_context",
        "risk_score",
        "credit_check",
        "medical_check",
        "driving_check",
        "fan_in_aggregator",
        "final_decision",
    } <= set(graph.nodes)


def test_decision_thresholds_remain_deterministic() -> None:
    assert compute_decision(0.82, {"risk": 0.7, "credit": 0.7}).value == "APPROVED"
    assert compute_decision(0.66, {"risk": 0.5, "credit": 0.7}).value == "APPROVED_WITH_CONDITIONS"
    assert (
        compute_decision(0.50, {"risk": 0.4, "credit": 0.4}).value == "REFER_TO_HUMAN_UNDERWRITER"
    )
    assert compute_decision(0.30, {"risk": 0.2, "credit": 0.2}).value == "DECLINED"
