from __future__ import annotations

import asyncio
import json
from contextlib import contextmanager
from typing import Any

import pytest

import foundry.main as hosted_main
from app.core.config import Settings
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository
from app.modules.underwriting.hosted import HOSTED_WORKFLOW_PROTOCOL


def _start_request() -> dict[str, Any]:
    return {
        "protocol": HOSTED_WORKFLOW_PROTOCOL,
        "workflow_run_id": "run-responses-test",
        "action": "start",
        "application": {
            "application_id": "app-responses-test",
            "applicant_name": "Responses Test",
            "age": 38,
            "income": 145000,
            "requested_coverage": 500000,
            "health_disclosures": "none",
            "driving_history": "clean",
            "credit_score": 760,
        },
        "options": {
            "fail_risk_once": True,
            "fail_credit_randomly": False,
            "crash_after_executor": None,
        },
    }


def _text_response(_context, _request, *, text: str):
    return json.loads(text)


def test_workflow_request_parses_responses_input_text_content() -> None:
    request = _start_request()

    result = hosted_main._workflow_request(
        {
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": json.dumps(request)}],
                }
            ]
        }
    )

    assert result == request


def test_workflow_request_parses_nested_responses_input_text_content() -> None:
    request = _start_request()

    result = hosted_main._workflow_request(
        {
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": {"value": json.dumps(request)},
                        }
                    ],
                }
            ]
        }
    )

    assert result == request


def test_workflow_request_parses_agent_server_context_input() -> None:
    request = _start_request()

    class Context:
        request_body = {
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": json.dumps(request)}],
                }
            ]
        }

    result = hosted_main._workflow_request({}, Context())

    assert result == request


def test_hosted_handler_executes_start_envelope(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    class FakeService:
        repository = type(
            "Repo", (), {"list_underwriting_results": staticmethod(lambda _run_id: [])}
        )()

        async def startup(self) -> None:
            return None

        async def shutdown(self) -> None:
            captured["shutdown"] = True

        def get_run(self, _workflow_run_id: str) -> None:
            return None

        async def start_run(self, **kwargs: Any):
            captured.update(kwargs)
            return {
                "workflow_run_id": kwargs["workflow_run_id"],
                "status": "COMPLETED",
                "outputs": [{"decision": "APPROVED", "rationale": "Hosted workflow rationale"}],
            }

    monkeypatch.setattr(hosted_main, "_local_service", lambda _settings: FakeService())

    result = asyncio.run(
        hosted_main._handle(
            {"input": json.dumps(_start_request())},
            context=None,
            text_response=_text_response,
        )
    )

    assert result["workflow_run_id"] == "run-responses-test"
    assert result["status"] == "COMPLETED"
    assert result["outputs"][0]["rationale"] == "Hosted workflow rationale"
    assert captured["application"].applicant_name == "Responses Test"
    assert captured["fail_risk_once"] is True
    assert captured["shutdown"] is True


def test_local_service_is_not_shared_between_hosted_invocations(monkeypatch) -> None:
    created: list[object] = []

    def build_service(_settings: Settings) -> object:
        service = object()
        created.append(service)
        return service

    monkeypatch.setattr(hosted_main, "build_underwriting_service", build_service)
    settings = hosted_main.load_settings()

    first = hosted_main._local_service(settings)
    second = hosted_main._local_service(settings)

    assert first is not second
    assert created == [first, second]


def test_hosted_handler_closes_service_when_startup_fails(monkeypatch) -> None:
    lifecycle: list[str] = []

    class FakeService:
        async def startup(self) -> None:
            lifecycle.append("startup")
            raise RuntimeError("startup failed")

        async def shutdown(self) -> None:
            lifecycle.append("shutdown")

    monkeypatch.setattr(hosted_main, "_local_service", lambda _settings: FakeService())

    with pytest.raises(RuntimeError, match="startup failed"):
        asyncio.run(
            hosted_main._handle(
                {"input": json.dumps(_start_request())},
                context=None,
                text_response=_text_response,
            )
        )

    assert lifecycle == ["startup", "shutdown"]


def test_hosted_handler_executes_resume_envelope(monkeypatch) -> None:
    captured: list[str] = []

    class FakeService:
        repository = type(
            "Repo", (), {"list_underwriting_results": staticmethod(lambda _run_id: [])}
        )()

        async def startup(self) -> None:
            return None

        async def shutdown(self) -> None:
            captured.append("shutdown")

        def get_run(self, _workflow_run_id: str) -> dict[str, str]:
            return {"status": "CRASHED"}

        async def resume_run(self, workflow_run_id: str) -> dict[str, Any]:
            captured.append(workflow_run_id)
            return {
                "workflow_run_id": workflow_run_id,
                "status": "COMPLETED",
                "outputs": [{"decision": "APPROVED"}],
            }

    monkeypatch.setattr(hosted_main, "_local_service", lambda _settings: FakeService())
    request = {
        "protocol": HOSTED_WORKFLOW_PROTOCOL,
        "workflow_run_id": "run-resume-test",
        "action": "resume",
    }

    result = asyncio.run(
        hosted_main._handle(
            {"input": json.dumps(request)},
            context=None,
            text_response=_text_response,
        )
    )

    assert captured == ["run-resume-test", "shutdown"]
    assert result == {
        "workflow_run_id": "run-resume-test",
        "status": "COMPLETED",
        "outputs": [{"decision": "APPROVED"}],
    }


def test_hosted_handler_runs_langgraph_workflow_and_resumes_checkpoint(monkeypatch) -> None:
    settings = Settings(
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
    monkeypatch.setattr(hosted_main, "load_settings", lambda: settings)
    start = _start_request()
    start["options"]["fail_risk_once"] = True
    start["options"]["crash_after_executor"] = "medical_check"

    crashed = asyncio.run(
        hosted_main._handle(
            {"input": json.dumps(start)},
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
                        "workflow_run_id": start["workflow_run_id"],
                        "action": "resume",
                    }
                )
            },
            context=None,
            text_response=_text_response,
        )
    )

    repository = WorkflowRunRepository()
    events = repository.list_events(start["workflow_run_id"])
    assert crashed["status"] == "CRASHED"
    assert repository.latest_checkpoint_id(start["workflow_run_id"]) is not None
    assert resumed["status"] == "COMPLETED"
    assert resumed["outputs"]
    assert any(event["event_type"] == "retry_attempt" for event in events)
    assert len([event for event in events if event["event_type"] == "fan_in_result_received"]) == 4


def test_hosted_handler_rejects_trace_only_metadata() -> None:
    result = asyncio.run(
        hosted_main._handle(
            {
                "input": [],
                "metadata": {
                    "workflow_run_id": "run-trace-only-metadata-test",
                    "execution_mode": "trace_only",
                },
            },
            context=None,
            text_response=_text_response,
        )
    )

    assert result["status"] == "REJECTED"


def test_hosted_handler_never_copies_application_values_to_manual_trace_attributes(
    monkeypatch,
) -> None:
    spans: list[dict[str, object]] = []

    class FakeSpan:
        def __init__(self, attributes: dict[str, object]) -> None:
            self.attributes = dict(attributes)
            spans.append(self.attributes)

        def set_attribute(self, key: str, value: object) -> None:
            self.attributes[key] = value

    class FakeTracer:
        @contextmanager
        def start_as_current_span(self, _name: str, *, attributes: dict[str, object]):
            yield FakeSpan(attributes)

    class FakeService:
        repository = type(
            "Repo", (), {"list_underwriting_results": staticmethod(lambda _run_id: [])}
        )()

        async def startup(self) -> None:
            return None

        async def shutdown(self) -> None:
            return None

        def get_run(self, _workflow_run_id: str) -> None:
            return None

        async def start_run(self, **kwargs: Any):
            return {
                "workflow_run_id": kwargs["workflow_run_id"],
                "status": "COMPLETED",
                "outputs": [],
            }

    monkeypatch.setattr(hosted_main, "_tracer", FakeTracer())
    monkeypatch.setattr(hosted_main, "_local_service", lambda _settings: FakeService())

    asyncio.run(
        hosted_main._handle(
            {"input": json.dumps(_start_request())},
            context=None,
            text_response=_text_response,
        )
    )

    trace_values = json.dumps(spans)
    assert "Responses Test" not in trace_values
    assert "145000" not in trace_values
    assert "760" not in trace_values
