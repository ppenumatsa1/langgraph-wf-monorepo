from __future__ import annotations

import asyncio
import json
from dataclasses import replace

from app.core.config import Settings
from app.infrastructure.foundry.responses_client import UnderwritingResponsesClient
from app.modules.underwriting.hosted import HostedWorkflowEnvelope
from app.modules.underwriting.models import UnderwritingApplication


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
        azure_ai_project_endpoint="https://example.services.ai.azure.com/api/projects/example",
        azure_client_id="client-id",
    )


def _application() -> UnderwritingApplication:
    return UnderwritingApplication(
        application_id="app-relay-test",
        applicant_name="Private Applicant",
        age=38,
        income=145000,
        requested_coverage=500000,
        health_disclosures="private medical detail",
        driving_history="private driving detail",
        credit_score=760,
    )


def test_hosted_client_sends_application_only_in_responses_input(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        output_text = json.dumps(
            {"workflow_run_id": "run-relay-test", "status": "COMPLETED", "outputs": []}
        )

    class FakeResponses:
        def create(self, *, input: object, metadata: object) -> FakeResponse:
            captured["input"] = input
            captured["metadata"] = metadata
            return FakeResponse()

    class FakeOpenAIClient:
        responses = FakeResponses()

    class FakeProjectClient:
        def __init__(self, **kwargs: object) -> None:
            captured["project_kwargs"] = kwargs

        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def get_openai_client(self, *, agent_name: str) -> FakeOpenAIClient:
            captured["agent_name"] = agent_name
            return FakeOpenAIClient()

    monkeypatch.setattr(
        "app.infrastructure.foundry.responses_client.AIProjectClient",
        FakeProjectClient,
    )
    monkeypatch.setattr(
        "app.infrastructure.foundry.responses_client.DefaultAzureCredential",
        lambda **kwargs: kwargs,
    )
    client = UnderwritingResponsesClient(_settings())

    result = asyncio.run(
        client.invoke(
            HostedWorkflowEnvelope(
                workflow_run_id="run-relay-test",
                action="start",
                application=_application(),
            )
        )
    )

    assert result["status"] == "COMPLETED"
    assert captured["agent_name"] == "underwriting-hosted"
    assert captured["project_kwargs"] == {
        "endpoint": "https://example.services.ai.azure.com/api/projects/example",
        "credential": {"managed_identity_client_id": "client-id"},
        "allow_preview": True,
    }
    assert captured["metadata"] == {
        "protocol": "underwriting-hosted-workflow/v1",
        "workflow_run_id": "run-relay-test",
        "action": "start",
        "hosted_agent_version": "",
    }
    assert "Private Applicant" in json.dumps(captured["input"])
    assert "private medical detail" not in json.dumps(captured["metadata"])
    assert "760" not in json.dumps(captured["metadata"])


def test_hosted_client_uses_configured_version_pinned_responses_url(monkeypatch) -> None:
    captured: dict[str, object] = {}
    token_provider = object()

    class FakeResponse:
        output_text = json.dumps(
            {"workflow_run_id": "run-url-test", "status": "COMPLETED", "outputs": []}
        )

    class FakeOpenAI:
        def __init__(self, **kwargs: object) -> None:
            captured["openai_kwargs"] = kwargs
            self.responses = self

        def create(self, *, input: object, metadata: object) -> FakeResponse:
            captured["input"] = input
            captured["metadata"] = metadata
            return FakeResponse()

    monkeypatch.setattr("app.infrastructure.foundry.responses_client.OpenAI", FakeOpenAI)
    monkeypatch.setattr(
        "app.infrastructure.foundry.responses_client.DefaultAzureCredential",
        lambda **kwargs: kwargs,
    )
    monkeypatch.setattr(
        "app.infrastructure.foundry.responses_client.get_bearer_token_provider",
        lambda credential, scope: token_provider,
    )
    settings = replace(
        _settings(),
        foundry_responses_endpoint=(
            "https://example.services.ai.azure.com/api/projects/example/"
            "agents/underwriting-hosted/endpoint/protocols/openai/responses?api-version=v1"
        ),
        foundry_hosted_agent_version="7",
    )

    result = asyncio.run(
        UnderwritingResponsesClient(settings).invoke(
            HostedWorkflowEnvelope(workflow_run_id="run-url-test", action="resume")
        )
    )

    assert result["workflow_run_id"] == "run-url-test"
    assert captured["openai_kwargs"] == {
        "api_key": token_provider,
        "base_url": (
            "https://example.services.ai.azure.com/api/projects/example/"
            "agents/underwriting-hosted/endpoint/protocols/openai/"
        ),
        "default_query": {"api-version": "v1"},
        "timeout": 60.0,
    }
    assert captured["metadata"] == {
        "protocol": "underwriting-hosted-workflow/v1",
        "workflow_run_id": "run-url-test",
        "action": "resume",
        "hosted_agent_version": "7",
    }
