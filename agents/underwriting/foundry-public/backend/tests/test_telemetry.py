from __future__ import annotations

from contextlib import contextmanager

from app.core import telemetry


def test_hosted_connection_string_prefers_application_specific_setting(monkeypatch) -> None:
    monkeypatch.setenv("UNDERWRITING_APPINSIGHTS_CONNECTION_STRING", "InstrumentationKey=custom")
    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "InstrumentationKey=reserved")

    assert telemetry._connection_string() == "InstrumentationKey=custom"


def test_hosted_observability_instruments_openai_once(monkeypatch) -> None:
    calls: list[object] = []

    class FakeOpenAIInstrumentor:
        def instrument(self) -> None:
            calls.append("openai")

    monkeypatch.setattr(telemetry, "_configured", False)
    monkeypatch.setenv("UNDERWRITING_APPINSIGHTS_CONNECTION_STRING", "InstrumentationKey=test")
    monkeypatch.setenv("OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT", "true")
    monkeypatch.setattr(
        telemetry,
        "configure_azure_monitor",
        lambda **kwargs: calls.append(kwargs),
    )
    monkeypatch.setattr(telemetry, "OpenAIInstrumentor", FakeOpenAIInstrumentor)

    telemetry.setup_hosted_observability()
    telemetry.setup_hosted_observability()

    assert calls[0]["sampling_ratio"] == 1.0
    assert calls[1:] == ["openai"]
    assert telemetry.os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] == "false"


def test_stage_span_marks_completion(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeSpan:
        def set_attribute(self, key: str, value: object) -> None:
            captured[key] = value

        def record_exception(self, exception: BaseException) -> None:
            captured["exception"] = exception

        def set_status(self, status: object) -> None:
            captured["status"] = status

    class FakeTracer:
        @contextmanager
        def start_as_current_span(self, name: str, *, attributes: dict[str, str]):
            captured["stage"] = name.removeprefix("workflow.")
            captured["attributes"] = attributes
            yield FakeSpan()

    monkeypatch.setattr(telemetry.trace, "get_tracer", lambda _name: FakeTracer())

    with telemetry.workflow_stage_span(
        "stage.risk_check",
        {
            "workflow.run_id": "run-123",
            "underwriting.application_id": "application-456",
            "underwriting.check_type": "risk",
            "workflow.executor": "risk_score",
        },
    ):
        pass

    assert captured["stage"] == "stage.risk_check"
    assert captured["attributes"] == {
        "workflow.run_id": "run-123",
        "underwriting.application_id": "application-456",
        "underwriting.check_type": "risk",
        "workflow.executor": "risk_score",
    }
    assert captured["workflow.status"] == "completed"


def test_stage_span_inherits_safe_workflow_context(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeSpan:
        def set_attribute(self, key: str, value: object) -> None:
            captured[key] = value

        def set_status(self, _status: object) -> None:
            pass

        def record_exception(self, _exception: BaseException) -> None:
            pass

    class FakeTracer:
        @contextmanager
        def start_as_current_span(self, _name: str, *, attributes: dict[str, str]):
            captured["attributes"] = attributes
            yield FakeSpan()

    monkeypatch.setattr(telemetry.trace, "get_tracer", lambda _name: FakeTracer())

    with telemetry.workflow_telemetry_context(
        {
            "workflow.run_id": "run-123",
            "workflow.action": "start",
            "gen_ai.agent.name": "underwriting-hosted",
        }
    ):
        with telemetry.workflow_stage_span("stage.risk_check", {"workflow.executor": "risk_score"}):
            pass

    assert captured["attributes"] == {
        "workflow.run_id": "run-123",
        "workflow.action": "start",
        "gen_ai.agent.name": "underwriting-hosted",
        "workflow.executor": "risk_score",
    }
