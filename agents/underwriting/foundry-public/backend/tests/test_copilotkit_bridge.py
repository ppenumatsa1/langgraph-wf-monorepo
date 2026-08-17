from __future__ import annotations

import asyncio
import json
from dataclasses import replace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import foundry.main as hosted_main
from app.api.v1.routers import copilotkit
from app.core.config import Settings
from app.modules.underwriting.copilot import SafeRunExplanationRequest
from app.modules.underwriting.copilot_bridge import UnderwritingCopilotBridge


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
    )


def test_bridge_forwards_only_allowlisted_selected_run_data() -> None:
    captured: dict[str, object] = {}
    private_prompt = "Private Applicant has chronic health details, income 145000, and score 760."

    class SafeRepository:
        @staticmethod
        def get_safe_run_status(_run_id: str) -> str:
            return "COMPLETED"

        @staticmethod
        def list_safe_event_summaries(_run_id: str, *, limit: int):
            assert limit == 100
            return [
                {
                    "event_type": "check_completed",
                    "executor_name": "risk_score",
                    "created_at": "2026-08-05T00:00:00Z",
                }
            ]

        @staticmethod
        def get_safe_checkpoint_summary(_run_id: str) -> tuple[int, str]:
            return 2, "2026-08-05T00:00:01Z"

        @staticmethod
        def get_safe_final_decision(_run_id: str) -> str:
            return "APPROVED"

    class HostedResponses:
        async def invoke(self, request: SafeRunExplanationRequest) -> dict[str, str]:
            captured.update(request.to_dict())
            return {
                "workflow_run_id": request.workflow_run_id,
                "explanation": private_prompt,
            }

    explanation = asyncio.run(
        UnderwritingCopilotBridge(
            _settings(),
            repository=SafeRepository(),
            responses_client=HostedResponses(),
        ).explain("run-copilot-safe", "summary")
    )

    captured_json = json.dumps(captured)
    assert private_prompt not in captured_json
    assert "applicant" not in captured_json.lower()
    assert "income" not in captured_json.lower()
    assert "rationale" not in captured_json.lower()
    assert '"workflow_run_id": "run-copilot-safe"' in captured_json
    assert "Private Applicant" not in explanation


def test_safe_explanation_request_rejects_unallowlisted_context_fields() -> None:
    request = {
        "protocol": "underwriting-safe-explanation/v1",
        "workflow_run_id": "run-safe-context",
        "intent": "summary",
        "context": {
            "workflow_run_id": "run-safe-context",
            "status": "COMPLETED",
            "events": [],
            "checkpoints": {"count": 0, "latest_created_at": None},
            "output": {"final_decision": None},
            "applicant_name": "must not pass the bridge",
        },
    }

    with pytest.raises(ValueError, match="Invalid safe selected run context"):
        SafeRunExplanationRequest.from_dict(request)


def test_hosted_safe_explanation_does_not_start_a_local_workflow(monkeypatch) -> None:
    class UnexpectedWorkflowService:
        pass

    request = SafeRunExplanationRequest.from_dict(
        {
            "protocol": "underwriting-safe-explanation/v1",
            "workflow_run_id": "run-hosted-explanation",
            "intent": "status",
            "context": {
                "workflow_run_id": "run-hosted-explanation",
                "status": "CRASHED",
                "events": [],
                "checkpoints": {"count": 1, "latest_created_at": "2026-08-05T00:00:00Z"},
                "output": {"final_decision": None},
            },
        }
    )
    monkeypatch.setattr(
        hosted_main, "_local_service", lambda _settings: UnexpectedWorkflowService()
    )

    result = asyncio.run(
        hosted_main._handle(
            {"input": json.dumps(request.to_dict())},
            context=None,
            text_response=lambda _context, _request, *, text: json.loads(text),
        )
    )

    assert result == {
        "workflow_run_id": "run-hosted-explanation",
        "status": "CRASHED",
        "explanation": "Run run-hosted-explanation is CRASHED.",
    }


def test_copilotkit_endpoint_requires_same_origin_and_streams_agui(monkeypatch) -> None:
    calls: list[tuple[str | None, str]] = []
    private_prompt = "Do not repeat applicant name or credit score 760."

    class FakeBridge:
        async def explain(self, workflow_run_id: str | None, intent: str) -> str:
            calls.append((workflow_run_id, intent))
            return "Run run-copilot-contract is COMPLETED."

    monkeypatch.setattr(copilotkit, "bridge", FakeBridge())
    monkeypatch.setattr(
        copilotkit,
        "load_settings",
        lambda: replace(_settings(), frontend_origin="https://frontend.example"),
    )
    app = FastAPI()
    app.include_router(copilotkit.router)
    payload = {
        "threadId": "thread-copilot-contract",
        "runId": "run-copilot-chat",
        "state": {},
        "messages": [{"id": "message-1", "role": "user", "content": private_prompt}],
        "context": [
            {
                "description": "selected run",
                "value": json.dumps(
                    {
                        "runId": "run-copilot-contract",
                        "applicantName": "Private Applicant",
                        "creditScore": 760,
                    }
                ),
            }
        ],
    }

    with TestClient(app) as client:
        runtime_info = client.get("/api/v1/underwriting/copilotkit/info")
        rejected = client.post(
            "/api/v1/underwriting/copilotkit/agent/underwriting-run-assistant/run",
            headers={"origin": "https://untrusted.example"},
            json=payload,
        )
        response = client.post(
            "/api/v1/underwriting/copilotkit/agent/underwriting-run-assistant/run",
            headers={"origin": "https://frontend.example", "accept": "text/event-stream"},
            json=payload,
        )

    assert runtime_info.json() == {
        "version": "1.0",
        "mode": "sse",
        "audioFileTranscriptionEnabled": False,
        "threadEndpoints": {
            "list": False,
            "inspect": False,
            "mutations": False,
            "realtimeMetadata": False,
        },
        "agents": {
            "underwriting-run-assistant": {
                "name": "Underwriting Run Assistant",
                "className": "UnderwritingRunAssistant",
                "description": "Explains the allowlisted status and execution history of an underwriting run.",
            }
        },
    }
    assert rejected.status_code == 403
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert '"type":"RUN_STARTED"' in response.text
    assert '"type":"TEXT_MESSAGE_START"' in response.text
    assert '"type":"TEXT_MESSAGE_CONTENT"' in response.text
    assert '"type":"RUN_FINISHED"' in response.text
    assert private_prompt not in response.text
    assert "Private Applicant" not in response.text
    assert "760" not in response.text
    assert calls == [("run-copilot-contract", "summary")]
