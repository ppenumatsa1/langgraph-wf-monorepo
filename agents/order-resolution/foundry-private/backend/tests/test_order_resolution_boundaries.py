from __future__ import annotations

import json
import os
from pathlib import Path
from uuid import uuid4

from app.modules.order_resolution.agui import (
    native_agui_events_for_workflow_event,
)
from app.modules.order_resolution.models import WorkflowEvent
from app.modules.order_resolution.rich_events import rich_envelope_for_workflow_event


def test_runtime_boundary_has_no_agent_framework_imports() -> None:
    backend = Path(__file__).resolve().parents[1]
    application_sources = "\n".join(
        path.read_text(encoding="utf-8") for path in (backend / "app").rglob("*.py")
    )

    assert "agent_framework" not in application_sources
    assert "app.maf" not in application_sources
    assert not (backend / "app" / "maf").exists()
    assert (backend / "app" / "langgraph").is_dir()


def test_langgraph_checkpoint_deserialization_is_strict() -> None:
    from app import langgraph as app_langgraph
    from langgraph.checkpoint.serde import _msgpack

    assert app_langgraph.OrderResolutionState is not None
    assert os.environ["LANGGRAPH_STRICT_MSGPACK"] == "true"
    assert _msgpack.STRICT_MSGPACK_ENABLED is True


def test_agui_projection_redacts_native_sensitive_payloads() -> None:
    checkpoint_id = str(uuid4())
    native = WorkflowEvent(
        type="tool.call",
        thread_id="thread-safe",
        payload={
            "local_tool": "fetch_order_status/fetch_policy",
            "order": {"order_id": "ord-1009", "total_amount": 185.0},
            "policy": "refund_allowed_if_delay_exceeds_3_days",
            "mcp_result": {"secret": "do-not-expose"},
            "checkpoint_id": checkpoint_id,
            "prompt": "private prompt",
        },
    )

    serialized = json.dumps(native_agui_events_for_workflow_event(native)).lower()

    assert "policy-lookup" in serialized
    assert "ord-1009" not in serialized
    assert "refund_allowed" not in serialized
    assert "do-not-expose" not in serialized
    assert "private prompt" not in serialized


def test_native_event_names_remain_stable() -> None:
    event_source = (
        Path(__file__).resolve().parents[1] / "app/modules/order_resolution/events.py"
    ).read_text(encoding="utf-8")

    for event_name in (
        "workflow.stage",
        "tool.call",
        "checkpoint.created",
        "hitl.request",
        "hitl.response",
        "workflow.output",
    ):
        assert event_name in event_source


def test_rich_event_source_matches_frontend_contract() -> None:
    envelope = rich_envelope_for_workflow_event(
        WorkflowEvent(
            type="workflow.output",
            thread_id="thread-safe",
            payload={"message": "Workflow completed."},
        ),
        sequence=1,
    )

    assert envelope["type"] == "workflow.rich"
    assert envelope["source"] == "langgraph-order-resolution"
