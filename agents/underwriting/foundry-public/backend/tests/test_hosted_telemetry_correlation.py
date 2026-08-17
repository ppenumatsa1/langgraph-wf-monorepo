from __future__ import annotations

import asyncio
import json
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

import app.infrastructure.persistence.checkpoint_store as checkpoint_module
import app.langgraph.nodes as nodes_module
import app.langgraph.runtime as runtime_module
import foundry.main as hosted_main
from app.core.config import Settings
from app.modules.underwriting.hosted import HOSTED_WORKFLOW_PROTOCOL


@dataclass
class _Span:
    name: str
    attributes: dict[str, object]
    parent: _Span | None

    def set_attribute(self, key: str, value: object) -> None:
        self.attributes[key] = value


@dataclass
class _CorrelationTracer:
    spans: list[_Span] = field(default_factory=list)
    _active: ContextVar[_Span | None] = field(
        default_factory=lambda: ContextVar("active_test_span", default=None)
    )

    @contextmanager
    def start_as_current_span(
        self, name: str, *, attributes: dict[str, object] | None = None, **_kwargs: object
    ):
        span = _Span(name, dict(attributes or {}), self._active.get())
        self.spans.append(span)
        token = self._active.set(span)
        try:
            yield span
        finally:
            self._active.reset(token)


def _settings() -> Settings:
    return Settings(
        db_host="",
        db_port=0,
        db_name="",
        db_user="",
        db_password="",
        log_level="WARNING",
        fail_risk_once=False,
        fail_credit_randomly=False,
        crash_after_executor="",
        crash_after_step_or_superstep="",
        retry_max_attempts=3,
        retry_base_delay_ms=1,
        retry_jitter_ms=0,
        azure_ai_project_id="",
        azure_ai_project_name="",
        foundry_model_deployment_name="",
        azure_openai_endpoint="",
        azure_openai_api_key="",
        database_url="postgresql://postgres:postgres@localhost:5433/underwriting_langgraph_test?sslmode=disable",
    )


def _request() -> dict[str, object]:
    return {
        "protocol": HOSTED_WORKFLOW_PROTOCOL,
        "workflow_run_id": "run-trace-correlation",
        "action": "start",
        "application": {
            "application_id": "app-trace-correlation",
            "applicant_name": "Private Applicant",
            "age": 38,
            "income": 145000,
            "requested_coverage": 500000,
            "health_disclosures": "private health detail",
            "driving_history": "private driving detail",
            "credit_score": 760,
        },
        "options": {
            "fail_risk_once": True,
            "fail_credit_randomly": False,
            "crash_after_executor": "medical_check",
        },
    }


def _text_response(_context, _request, *, text: str):
    return json.loads(text)


def test_hosted_workflow_telemetry_is_correlated_to_responses_operation(monkeypatch) -> None:
    tracer = _CorrelationTracer()
    monkeypatch.setattr(hosted_main, "load_settings", _settings)
    monkeypatch.setattr(hosted_main, "_tracer", tracer)

    @contextmanager
    def stage_span(stage: str, attributes: dict[str, object] | None = None):
        with tracer.start_as_current_span(f"workflow.{stage}", attributes=attributes) as span:
            yield span

    monkeypatch.setattr(checkpoint_module, "workflow_stage_span", stage_span)
    monkeypatch.setattr(nodes_module, "workflow_stage_span", stage_span)
    monkeypatch.setattr(runtime_module, "workflow_stage_span", stage_span)

    crashed = asyncio.run(
        hosted_main._handle(
            {"input": json.dumps(_request())},
            context=None,
            text_response=_text_response,
        )
    )
    resumed = asyncio.run(
        hosted_main._handle(
            {
                "input": json.dumps(
                    {
                        "protocol": HOSTED_WORKFLOW_PROTOCOL,
                        "workflow_run_id": "run-trace-correlation",
                        "action": "resume",
                    }
                )
            },
            context=None,
            text_response=_text_response,
        )
    )

    assert crashed["status"] == "CRASHED"
    assert resumed["status"] == "COMPLETED"
    spans = {span.name: span for span in tracer.spans}
    required_spans = {
        "foundry.responses.invoke",
        "underwriting.hosted.workflow",
        "workflow.stage.init_context",
        "workflow.stage.risk_check",
        "workflow.stage.retry_attempt",
        "workflow.stage.retry_backoff",
        "workflow.stage.failure_injected",
        "workflow.stage.idempotency_skip",
        "workflow.checkpoint.save",
        "workflow.checkpoint.load",
        "workflow.stage.fan_in",
        "workflow.stage.final_decision",
    }
    assert required_spans <= spans.keys()
    response_span = spans["foundry.responses.invoke"]
    workflow_span = spans["underwriting.hosted.workflow"]
    assert workflow_span.parent is response_span
    input_messages = json.loads(str(response_span.attributes["gen_ai.input.messages"]))
    output_messages = json.loads(str(response_span.attributes["gen_ai.output.messages"]))
    assert input_messages == [
        {
            "role": "user",
            "parts": [{"type": "text", "content": "Execute underwriting workflow action: resume."}],
        }
    ]
    assert output_messages == [
        {
            "role": "assistant",
            "parts": [
                {
                    "type": "text",
                    "content": "Underwriting workflow finished with status: COMPLETED. Decision: APPROVED.",
                }
            ],
        }
    ]
    correlated = [
        span
        for span in tracer.spans
        if span.name.startswith("workflow.") and "workflow.run_id" in span.attributes
    ]
    assert correlated
    assert all(span.attributes["workflow.run_id"] == "run-trace-correlation" for span in correlated)
    assert all(
        "Private Applicant" not in json.dumps(span.attributes)
        and "145000" not in json.dumps(span.attributes)
        and "760" not in json.dumps(span.attributes)
        and "private health detail" not in json.dumps(span.attributes)
        for span in tracer.spans
    )
