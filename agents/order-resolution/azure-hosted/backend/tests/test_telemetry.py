from __future__ import annotations

import langchain_azure_ai.callbacks.tracers as azure_tracers
from app.core import telemetry


class _Span:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def is_recording(self) -> bool:
        return True

    def add_event(self, name, attributes=None) -> None:
        self.events.append((name, attributes or {}))


def test_sensitive_workflow_content_is_redacted_by_default(
    monkeypatch,
) -> None:
    monkeypatch.delenv("OTEL_RECORD_CONTENT", raising=False)

    attributes = telemetry._safe_attributes(
        {
            "workflow.thread_id": "thread-1",
            "message": "Order ORD-1009",
            "mcp_result": "private",
            "workflow.status": "completed",
        }
    )

    assert attributes == {
        "workflow.thread_id": "thread-1",
        "workflow.status": "completed",
    }


def test_langgraph_business_events_are_application_insights_safe(
    monkeypatch,
) -> None:
    span = _Span()
    monkeypatch.setattr(telemetry.trace, "get_current_span", lambda: span)

    telemetry.record_business_event(
        "langgraph.workflow.terminal",
        {
            "workflow.thread_id": "thread-1",
            "workflow.status": "completed",
            "output": "sensitive",
        },
    )

    assert span.events == [
        (
            "langgraph.workflow.terminal",
            {
                "workflow.thread_id": "thread-1",
                "workflow.status": "completed",
            },
        )
    ]


def test_observability_defaults_to_langgraph_service_name(
    monkeypatch,
) -> None:
    captured: dict[str, str] = {}
    monkeypatch.setenv("ENABLE_TELEMETRY", "true")
    monkeypatch.setenv("ENABLE_INSTRUMENTATION", "false")
    monkeypatch.delenv("OTEL_SERVICE_NAME", raising=False)
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    monkeypatch.delenv("APPINSIGHTS_CONNECTION_STRING", raising=False)
    monkeypatch.setattr(
        telemetry,
        "_create_observability_resource",
        lambda service_name: captured.setdefault("service_name", service_name),
    )
    monkeypatch.setattr(telemetry.trace, "set_tracer_provider", lambda provider: None)
    monkeypatch.setattr(telemetry, "TracerProvider", lambda resource=None: object())
    telemetry._reset_observability_for_tests()

    status = telemetry.setup_observability()

    assert status.telemetry_enabled is True
    assert captured["service_name"] == "langgraph-order-resolution"
    telemetry._reset_observability_for_tests()


def test_azure_monitor_exports_every_release_trace(monkeypatch) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setattr(
        "azure.monitor.opentelemetry.configure_azure_monitor",
        lambda **kwargs: captured.update(kwargs),
    )

    assert telemetry._configure_azure_monitor("InstrumentationKey=test", "resource") is True
    assert captured == {
        "connection_string": "InstrumentationKey=test",
        "resource": "resource",
        "sampling_ratio": 1.0,
    }


def test_langgraph_auto_tracing_redacts_content_and_reuses_provider(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}
    monkeypatch.setenv("ENABLE_TELEMETRY", "true")
    monkeypatch.setenv("ENABLE_INSTRUMENTATION", "true")
    monkeypatch.setenv("ENABLE_LANGGRAPH_AUTO_TRACING", "true")
    monkeypatch.setattr(
        azure_tracers,
        "enable_auto_tracing",
        lambda **kwargs: captured.update(kwargs),
    )

    assert telemetry.enable_langgraph_auto_tracing() is True
    assert captured == {
        "enable_content_recording": False,
        "trace_all_langgraph_nodes": True,
        "auto_configure_azure_monitor": False,
        "trace_state": False,
    }
