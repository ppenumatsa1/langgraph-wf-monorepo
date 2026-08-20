from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from app.langgraph.state import OrderResolutionState
from app.modules.order_resolution.models import PendingApprovalError
from langchain_azure_ai.agents.hosting import ResponsesHostServer

os.environ.setdefault("OTEL_TRACES_EXPORTER", "none")
os.environ.setdefault("OTEL_METRICS_EXPORTER", "none")
os.environ.setdefault("OTEL_LOGS_EXPORTER", "none")
os.environ.setdefault("FOUNDRY_HOSTED_SKIP_APP_INIT_FOR_TESTS", "true")

from foundry import main as foundry_main


class _FakeTextResponse:
    def __init__(self, context: object, request: object, *, text: str) -> None:
        self.context = context
        self.request = request
        self.text = text


class _FakeRepository:
    def __init__(self) -> None:
        self.details_by_thread: dict[str, object] = {}

    def get_workflow_run(self, thread_id: str) -> object | None:
        return self.details_by_thread.get(thread_id)


class _FakeService:
    def __init__(self) -> None:
        self.started: list[dict[str, str]] = []
        self.resumed: list[dict[str, str]] = []

    async def start_chat_run(self, request: object) -> object:
        self.started.append(
            {
                "thread_id": request.thread_id,  # type: ignore[attr-defined]
                "session_id": request.session_id,  # type: ignore[attr-defined]
                "message": request.message,  # type: ignore[attr-defined]
                "customer_id": request.customer_id,  # type: ignore[attr-defined]
            }
        )
        return SimpleNamespace(run_id="run-1", thread_id=request.thread_id)

    async def respond_hitl(self, request: object) -> object:
        self.resumed.append(
            {
                "checkpoint_id": request.checkpoint_id,  # type: ignore[attr-defined]
                "decision": request.decision,  # type: ignore[attr-defined]
            }
        )
        return SimpleNamespace(accepted=True, checkpoint_id=request.checkpoint_id, thread_id="C1")


class _FakeSpan:
    def __init__(self, name: str) -> None:
        self.name = name
        self.attributes: dict[str, str | bool | int | float] = {}
        self.recorded_exceptions: list[Exception] = []

    def __enter__(self) -> _FakeSpan:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> bool:
        return False

    def set_attribute(self, key: str, value: str | bool | int | float) -> None:
        self.attributes[key] = value

    def record_exception(self, exc: Exception) -> None:
        self.recorded_exceptions.append(exc)


class _FakeTracer:
    def __init__(self) -> None:
        self.spans: list[_FakeSpan] = []

    def start_as_current_span(self, name: str) -> _FakeSpan:
        span = _FakeSpan(name)
        self.spans.append(span)
        return span


class _FakeResponsesHost:
    instances: list[_FakeResponsesHost] = []

    def __init__(self, **kwargs: object) -> None:
        self.store_supplied = "store" in kwargs
        self.store = kwargs.get("store")
        self.handler: object | None = None
        self.instances.append(self)

    def response_handler(self, handler: object) -> None:
        self.handler = handler


def _details(
    *,
    thread_id: str,
    status: str,
    pending: list[dict[str, str]] | None = None,
    output_message: str = "",
) -> object:
    events = [
        SimpleNamespace(
            model_dump=lambda: {
                "id": "evt-1",
                "type": "workflow.stage",
                "thread_id": thread_id,
                "payload": {"agent": "triage", "status": "completed"},
            }
        ),
        SimpleNamespace(
            model_dump=lambda: {
                "id": "evt-2",
                "type": "tool.call",
                "thread_id": thread_id,
                "payload": {"local_tool": "fetch_order_status/fetch_policy"},
            }
        ),
    ]
    pending_models = [
        SimpleNamespace(
            status=item["status"], checkpoint_id=item["checkpoint_id"], model_dump=lambda i=item: i
        )
        for item in (pending or [])
    ]
    latest_output = {"message": output_message} if output_message else None
    return SimpleNamespace(
        thread_id=thread_id,
        status=status,
        events=events,
        pending_approvals=pending_models,
        latest_output=latest_output,
    )


def _fake_responses_types() -> tuple[
    type[object], type[object], type[object], type[object], type[object]
]:
    return (
        _FakeResponsesHost,
        object,
        object,
        _FakeTextResponse,
        object,
    )


def test_hosted_manifest_configures_responses_and_model_settings() -> None:
    manifest = Path(__file__).parents[2] / "infra" / "foundry-hosted" / "azure.yaml"
    manifest_text = manifest.read_text()

    assert "AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING" not in manifest_text
    assert 'OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT: "false"' in manifest_text
    assert "language: docker" in manifest_text
    assert "AZURE_AI_MODEL_DEPLOYMENT_NAME: ${FOUNDRY_MODEL_DEPLOYMENT_NAME}" in manifest_text
    assert "TRACE_EVALUATION_RECORD_CONTENT: ${FOUNDRY_TRACE_EVALUATION_RECORD_CONTENT}" in (
        manifest_text
    )
    assert "FOUNDRY_PROJECTS_ENDPOINT:" not in manifest_text
    assert "FOUNDRY_RUNTIME_DATABASE_URL:" not in manifest_text
    assert "\n            DATABASE_URL:" not in manifest_text
    assert "\n            RUNTIME_DATABASE_URL:" not in manifest_text
    assert not hasattr(foundry_main, "setup_observability")


def test_foundry_model_env_aliases_set_canonical_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("FOUNDRY_PROJECTS_ENDPOINT", raising=False)
    monkeypatch.delenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", raising=False)
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://example.test/api/projects/order")
    monkeypatch.setenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4o-mini")

    foundry_main._apply_foundry_model_env_aliases()

    assert os.getenv("FOUNDRY_PROJECTS_ENDPOINT") == "https://example.test/api/projects/order"
    assert os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME") == "gpt-4o-mini"


def test_foundry_model_env_aliases_preserve_canonical_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FOUNDRY_PROJECTS_ENDPOINT", "https://canonical.test/api/projects/order")
    monkeypatch.setenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "canonical-model")
    monkeypatch.setenv("FOUNDRY_PROJECT_ENDPOINT", "https://hosted.test/api/projects/order")
    monkeypatch.setenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "hosted-model")

    foundry_main._apply_foundry_model_env_aliases()

    assert os.getenv("FOUNDRY_PROJECTS_ENDPOINT") == "https://canonical.test/api/projects/order"
    assert os.getenv("FOUNDRY_MODEL_DEPLOYMENT_NAME") == "canonical-model"


def test_build_app_uses_foundry_managed_response_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _FakeResponsesHost.instances.clear()
    monkeypatch.setattr(foundry_main, "_load_responses_types", _fake_responses_types)

    app = foundry_main._build_app()

    assert app is _FakeResponsesHost.instances[-1]
    assert app.store_supplied is False


def test_responses_host_server_default_converter_rejects_custom_state() -> None:
    graph = SimpleNamespace(
        builder=SimpleNamespace(state_schema=OrderResolutionState),
        checkpointer=object(),
    )

    with pytest.warns(UserWarning), pytest.raises(ValueError, match="messages"):
        ResponsesHostServer(graph)


def test_hosted_provider_initializes_before_langgraph_auto_tracing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    order: list[str] = []
    hosted_app = object()
    monkeypatch.setattr(
        foundry_main,
        "_build_app",
        lambda: order.append("agentserver") or hosted_app,
    )
    monkeypatch.setattr(
        foundry_main._telemetry,
        "enable_langgraph_auto_tracing",
        lambda: order.append("langgraph") or True,
    )

    assert foundry_main._initialize_app() is hosted_app
    assert order == ["agentserver", "langgraph"]


def test_runtime_database_url_override_sets_database_url_when_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    runtime_url = (
        "postgresql://user:pass@server.postgres.database.azure.com:5432/maf?sslmode=require"
    )
    monkeypatch.setenv("RUNTIME_DATABASE_URL", runtime_url)

    foundry_main._apply_runtime_database_url_override()

    assert os.getenv("DATABASE_URL") == runtime_url


def test_runtime_database_url_override_prefers_foundry_runtime_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv(
        "FOUNDRY_RUNTIME_DATABASE_URL",
        "postgresql://user:pass@preferred.postgres.database.azure.com:5432/maf?sslmode=require",
    )
    monkeypatch.setenv(
        "RUNTIME_DATABASE_URL",
        "postgresql://user:pass@fallback.postgres.database.azure.com:5432/maf?sslmode=require",
    )

    foundry_main._apply_runtime_database_url_override()

    assert os.getenv("DATABASE_URL", "").startswith(
        "postgresql://user:pass@preferred.postgres.database.azure.com"
    )


def test_runtime_database_url_override_replaces_loopback_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_url = (
        "postgresql://user:pass@server.postgres.database.azure.com:5432/maf?sslmode=require"
    )
    monkeypatch.setenv("RUNTIME_DATABASE_URL", runtime_url)
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@127.0.0.1:5432/langgraph_workflow",
    )

    foundry_main._apply_runtime_database_url_override()

    assert os.getenv("DATABASE_URL") == runtime_url


def test_runtime_database_url_override_replaces_connection_placeholder(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime_url = "******server.postgres.database.azure.com:5432/maf?sslmode=require"
    monkeypatch.setenv("RUNTIME_DATABASE_URL", runtime_url)
    monkeypatch.setenv(
        "DATABASE_URL",
        "${{connections.orderresolutionruntimesecrets.credentials.database_url}}",
    )

    foundry_main._apply_runtime_database_url_override()

    assert os.getenv("DATABASE_URL") == runtime_url


def test_runtime_database_url_override_keeps_existing_remote_database_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    existing_url = (
        "postgresql://user:pass@existing.postgres.database.azure.com:5432/maf?sslmode=require"
    )
    runtime_url = (
        "postgresql://user:pass@server.postgres.database.azure.com:5432/maf?sslmode=require"
    )
    monkeypatch.setenv("DATABASE_URL", existing_url)
    monkeypatch.setenv("RUNTIME_DATABASE_URL", runtime_url)

    foundry_main._apply_runtime_database_url_override()

    assert os.getenv("DATABASE_URL") == existing_url


def test_appinsights_env_alias_sets_canonical_connection_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("APPLICATIONINSIGHTS_CONNECTION_STRING", raising=False)
    monkeypatch.setenv(
        "APPINSIGHTS_CONNECTION_STRING",
        "InstrumentationKey=12345678-1234-1234-1234-1234567890ab;IngestionEndpoint=https://eastus2-3.in.applicationinsights.azure.com/;LiveEndpoint=https://eastus2.livediagnostics.monitor.azure.com/;ApplicationId=f3bf2e8e-9ca7-433c-ab54-0a886618d564",
    )

    foundry_main._apply_appinsights_connection_env_aliases()

    assert os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING") == (
        "InstrumentationKey=12345678-1234-1234-1234-1234567890ab"
    )


def test_appinsights_env_alias_preserves_existing_canonical_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "APPLICATIONINSIGHTS_CONNECTION_STRING",
        "InstrumentationKey=aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb",
    )
    monkeypatch.setenv(
        "APPINSIGHTS_CONNECTION_STRING",
        "InstrumentationKey=cccccccc-1111-2222-3333-dddddddddddd",
    )

    foundry_main._apply_appinsights_connection_env_aliases()

    assert os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING") == (
        "InstrumentationKey=aaaaaaaa-1111-2222-3333-bbbbbbbbbbbb"
    )


def test_parse_input_extracts_conversation_and_message() -> None:
    parsed = foundry_main._parse_input(
        {
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": "Resolve delayed order ORD-1001"}],
                }
            ],
            "conversation": {"id": "C1"},
        },
        None,
    )
    assert parsed.conversation_id == "C1"
    assert parsed.message == "Resolve delayed order ORD-1001"
    assert parsed.decision is None
    assert parsed.checkpoint_id is None


def test_parse_input_detects_function_call_output_decision() -> None:
    parsed = foundry_main._parse_input(
        {
            "conversation_id": "C1",
            "input": [
                {
                    "type": "function_call_output",
                    "call_id": "cp-123",
                    "output": {"decision": "approve"},
                }
            ],
        },
        None,
    )
    assert parsed.decision == "approve"
    assert parsed.checkpoint_id == "cp-123"


def test_parse_input_detects_explicit_top_level_resume_fields() -> None:
    parsed = foundry_main._parse_input(
        {
            "conversation": {"id": "C1"},
            "input": "Approve",
            "decision": "approve",
            "checkpoint_id": "cp-123",
        },
        None,
    )

    assert parsed.decision == "approve"
    assert parsed.checkpoint_id == "cp-123"


def test_parse_input_detects_forwarded_client_header_resume_fields() -> None:
    parsed = foundry_main._parse_input(
        {"conversation": {"id": "C1"}, "input": "Approve"},
        SimpleNamespace(
            client_headers={
                "X-Client-Decision": "approve",
                "X-Client-Checkpoint-Id": "cp-123",
            }
        ),
    )

    assert parsed.decision == "approve"
    assert parsed.checkpoint_id == "cp-123"


def test_serialize_workflow_gives_pending_approval_an_assistant_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _FakeRepository()
    repo.details_by_thread["C1"] = _details(
        thread_id="C1",
        status="waiting_approval",
        pending=[{"checkpoint_id": "cp-123", "status": "pending"}],
    )
    monkeypatch.setattr(foundry_main, "workflow_run_repository", repo)

    payload = foundry_main._serialize_workflow("C1")

    assert payload["message"] == "Approval is required before this order resolution can continue."


def test_parse_input_extracts_message_from_context_when_payload_is_empty() -> None:
    parsed = foundry_main._parse_input(
        {},
        SimpleNamespace(
            conversation_id="C2",
            request_body={
                "input": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "input_text", "text": "Resolve delayed order ORD-1001"}
                        ],
                    }
                ]
            },
        ),
    )
    assert parsed.conversation_id == "C2"
    assert parsed.message == "Resolve delayed order ORD-1001"
    assert parsed.decision is None


def test_parse_input_prefers_payload_response_id_over_context_session_id() -> None:
    parsed = foundry_main._parse_input(
        {"id": "resp-123", "input": "Resolve delayed order ORD-1001"},
        SimpleNamespace(session_id="sess-abc"),
    )
    assert parsed.conversation_id == "resp-123"


def test_parse_input_accepts_previous_response_id_for_resume(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _FakeRepository()
    repo.details_by_thread["resp-prev-1"] = _details(
        thread_id="resp-prev-1",
        status="waiting_approval",
        pending=[{"checkpoint_id": "cp-123", "status": "pending"}],
    )
    monkeypatch.setattr(foundry_main, "workflow_run_repository", repo)

    parsed = foundry_main._parse_input(
        {"previous_response_id": "resp-prev-1", "input": "Approve"},
        None,
    )
    assert parsed.conversation_id == "resp-prev-1"
    assert parsed.decision == "approve"


def test_parse_input_prefers_payload_conversation_string_over_previous_response_id() -> None:
    parsed = foundry_main._parse_input(
        {
            "conversation": "conv-456",
            "previous_response_id": "resp-prev-2",
            "input": "Resolve delayed order ORD-1001",
        },
        None,
    )
    assert parsed.conversation_id == "conv-456"


def test_parse_input_extracts_conversation_id_from_context_request_metadata() -> None:
    parsed = foundry_main._parse_input(
        {"id": "resp-123", "input": "Resolve delayed order ORD-1009"},
        SimpleNamespace(request_body={"metadata": {"conversation_id": "conv-meta-1"}}),
    )
    assert parsed.conversation_id == "resp-123"


def test_parse_input_prefers_context_request_metadata_over_context_id() -> None:
    parsed = foundry_main._parse_input(
        {"input": "Resolve delayed order ORD-1001"},
        SimpleNamespace(
            id="resp-999", request_body={"metadata": {"conversation_id": "conv-meta-2"}}
        ),
    )
    # Strict responses-native mode no longer uses metadata/context.id fallback.
    UUID(parsed.conversation_id)


def test_parse_input_uses_payload_conversation_id_when_present() -> None:
    parsed = foundry_main._parse_input(
        {
            "id": "resp-123",
            "conversation": {"id": "conv-123"},
            "input": "Resolve delayed order ORD-1001",
        },
        None,
    )
    assert parsed.conversation_id == "conv-123"


def test_parse_input_detects_approval_from_nested_value_shapes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _FakeRepository()
    repo.details_by_thread["conv-approve-1"] = _details(
        thread_id="conv-approve-1",
        status="waiting_approval",
        pending=[{"checkpoint_id": "cp-123", "status": "pending"}],
    )
    monkeypatch.setattr(foundry_main, "workflow_run_repository", repo)

    parsed = foundry_main._parse_input(
        {
            "conversation": {"id": "conv-approve-1"},
            "input": [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": {"value": "Approve"}}],
                }
            ],
        },
        None,
    )
    assert parsed.message == "Approve"
    assert parsed.decision == "approve"


def test_parse_input_detects_approval_from_serialized_context_input() -> None:
    context = SimpleNamespace(
        conversation_id="conv-approve-2",
        input="{'conversation': {'id': 'conv-approve-2'}, 'input': 'Approve'}",
    )
    parsed = foundry_main._parse_input({}, context)
    assert parsed.conversation_id == "conv-approve-2"
    assert parsed.decision is None


@pytest.mark.parametrize(
    "message",
    [
        "Yes, the order is still delayed.",
        "No, I have not received it.",
        "Please approve a refund after checking the order.",
        "Do not reject this ordinary support message.",
    ],
)
@pytest.mark.parametrize("has_pending", [False, True])
def test_parse_input_does_not_classify_descriptive_confirmation_words(
    monkeypatch: pytest.MonkeyPatch,
    message: str,
    has_pending: bool,
) -> None:
    repo = _FakeRepository()
    if has_pending:
        repo.details_by_thread["C1"] = _details(
            thread_id="C1",
            status="waiting_approval",
            pending=[{"checkpoint_id": "cp-123", "status": "pending"}],
        )
    monkeypatch.setattr(foundry_main, "workflow_run_repository", repo)

    parsed = foundry_main._parse_input(
        {"conversation": {"id": "C1"}, "input": message},
        None,
    )

    assert parsed.decision is None


@pytest.mark.parametrize(
    ("message", "expected"),
    [("Yes.", "approve"), ("Approve", "approve"), ("No", "reject"), ("Rejected!", "reject")],
)
def test_parse_input_accepts_only_whole_message_pending_confirmation(
    monkeypatch: pytest.MonkeyPatch,
    message: str,
    expected: str,
) -> None:
    repo = _FakeRepository()
    repo.details_by_thread["C1"] = _details(
        thread_id="C1",
        status="waiting_approval",
        pending=[{"checkpoint_id": "cp-123", "status": "pending"}],
    )
    monkeypatch.setattr(foundry_main, "workflow_run_repository", repo)

    parsed = foundry_main._parse_input(
        {"conversation": {"id": "C1"}, "input": message},
        None,
    )

    assert parsed.decision == expected


def test_parse_input_does_not_accept_confirmation_without_pending_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(foundry_main, "workflow_run_repository", _FakeRepository())

    parsed = foundry_main._parse_input(
        {"conversation": {"id": "C1"}, "input": "Approve"},
        None,
    )

    assert parsed.decision is None


def test_parse_input_resume_hitl_without_decision_does_not_auto_approve() -> None:
    parsed = foundry_main._parse_input(
        {"conversation_id": "C1", "metadata": {"operation": "resume_hitl"}},
        None,
    )
    assert parsed.decision is None


@pytest.mark.parametrize(
    "message",
    [
        "Yes",
        "Yes, approve it",
        "No",
        "No, reject it",
    ],
)
def test_parse_input_does_not_map_confirmation_without_pending_projection(
    monkeypatch: pytest.MonkeyPatch,
    message: str,
) -> None:
    monkeypatch.setattr(foundry_main, "workflow_run_repository", _FakeRepository())
    parsed = foundry_main._parse_input(
        {"previous_response_id": "resp-prev-yes-no", "input": message},
        None,
    )

    assert parsed.conversation_id == "resp-prev-yes-no"
    assert parsed.message == message
    assert parsed.decision is None


@pytest.mark.parametrize(
    "message",
    ["Yes, approve it", "No, reject it"],
)
def test_parse_input_rejects_non_strict_confirmation_with_pending_previous_response(
    monkeypatch: pytest.MonkeyPatch,
    message: str,
) -> None:
    repo = _FakeRepository()
    repo.details_by_thread["resp-prev-yes-no"] = _details(
        thread_id="resp-prev-yes-no",
        status="waiting_approval",
        pending=[{"checkpoint_id": "cp-123", "status": "pending"}],
    )
    monkeypatch.setattr(foundry_main, "workflow_run_repository", repo)

    parsed = foundry_main._parse_input(
        {"previous_response_id": "resp-prev-yes-no", "input": message},
        None,
    )

    assert parsed.conversation_id == "resp-prev-yes-no"
    assert parsed.message == message
    assert parsed.decision is None


@pytest.mark.asyncio
async def test_run_from_responses_starts_workflow_and_returns_serialized_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _FakeRepository()
    service = _FakeService()
    repo.details_by_thread["C1"] = _details(
        thread_id="C1",
        status="completed",
        output_message="Resolution complete. Action 'issue_partial_refund' submitted for order ord-1001.",
    )
    monkeypatch.setattr(foundry_main, "workflow_run_repository", repo)
    monkeypatch.setattr(foundry_main, "order_resolution_service", service)

    response = await foundry_main._run_from_responses(
        {"conversation": {"id": "C1"}, "input": "Resolve delayed order ORD-1001"},
        None,
        _FakeTextResponse,
    )

    payload = json.loads(response.text)
    assert service.started == [
        {
            "thread_id": "C1",
            "session_id": "C1",
            "message": "Resolve delayed order ORD-1001",
            "customer_id": "foundry-private-hosted",
        }
    ]
    assert payload["thread_id"] == "C1"
    assert payload["status"] == "completed"
    assert any(event["type"] == "tool.call" for event in payload["events"])


@pytest.mark.asyncio
async def test_run_from_responses_resumes_pending_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _FakeRepository()
    service = _FakeService()
    tracer = _FakeTracer()
    repo.details_by_thread["C1"] = _details(
        thread_id="C1",
        status="waiting_approval",
        pending=[{"checkpoint_id": "cp-123", "status": "pending"}],
    )
    monkeypatch.setattr(foundry_main, "workflow_run_repository", repo)
    monkeypatch.setattr(foundry_main, "order_resolution_service", service)
    monkeypatch.setattr(foundry_main, "get_tracer", lambda _: tracer)
    monkeypatch.delenv("FOUNDRY_HOSTED_AGENT_NAME", raising=False)
    monkeypatch.delenv("FOUNDRY_HOSTED_AGENT_ID", raising=False)

    await foundry_main._run_from_responses(
        {
            "conversation": {"id": "C1"},
            "input": [{"type": "function_call_output", "call_id": "cp-123", "output": "approve"}],
        },
        None,
        _FakeTextResponse,
    )

    assert service.resumed == [{"checkpoint_id": "cp-123", "decision": "approve"}]
    span = tracer.spans[0]
    assert span.name == "foundry.responses.invoke"
    assert span.attributes["workflow.thread_id"] == "C1"
    assert span.attributes["workflow.session_id"] == "C1"
    assert span.attributes["foundry.protocol"] == "responses"
    assert span.attributes["workflow.checkpoint_id"] == "cp-123"
    assert span.attributes["workflow.status"] == "waiting_approval"
    assert span.attributes["workflow.event_count"] == 2
    assert span.attributes["gen_ai.operation.name"] == "invoke_agent"
    assert span.attributes["gen_ai.agent.name"] == "order-resolution-private-hosted"
    assert span.attributes["gen_ai.agent.id"] == "order-resolution-private-hosted"
    assert span.attributes["gen_ai.conversation.id"] == "C1"
    assert span.attributes["deployment.lane"] == "foundry-private"


@pytest.mark.asyncio
async def test_run_from_responses_reconciles_before_text_confirmation_parse(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _FakeRepository()

    class _ReconcilingService(_FakeService):
        async def startup(self) -> None:
            repo.details_by_thread["C1"] = _details(
                thread_id="C1",
                status="waiting_approval",
                pending=[{"checkpoint_id": "cp-123", "status": "pending"}],
            )

    service = _ReconcilingService()
    monkeypatch.setattr(foundry_main, "workflow_run_repository", repo)
    monkeypatch.setattr(foundry_main, "order_resolution_service", service)
    monkeypatch.setattr(foundry_main, "get_tracer", lambda _: _FakeTracer())

    await foundry_main._run_from_responses(
        {"conversation": {"id": "C1"}, "input": "Approve"},
        None,
        _FakeTextResponse,
    )

    assert service.resumed == [{"checkpoint_id": "cp-123", "decision": "approve"}]


@pytest.mark.asyncio
async def test_run_from_responses_routes_normal_turn_to_pending_approval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _PendingService:
        async def start_chat_run(self, request: object) -> object:
            raise PendingApprovalError("C1", "cp-123")

    repo = _FakeRepository()
    repo.details_by_thread["C1"] = _details(
        thread_id="C1",
        status="waiting_approval",
        pending=[{"checkpoint_id": "cp-123", "status": "pending"}],
    )
    monkeypatch.setattr(foundry_main, "workflow_run_repository", repo)
    monkeypatch.setattr(foundry_main, "order_resolution_service", _PendingService())
    monkeypatch.setattr(foundry_main, "get_tracer", lambda _: _FakeTracer())

    response = await foundry_main._run_from_responses(
        {"conversation": {"id": "C1"}, "input": "Start another request."},
        None,
        _FakeTextResponse,
    )
    payload = json.loads(response.text)

    assert payload["status"] == "waiting_approval"
    assert "pending approval" in payload["message"].lower()


@pytest.mark.asyncio
async def test_run_from_responses_records_exception_on_root_span(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FailingService:
        async def start_chat_run(self, request: object) -> object:
            raise RuntimeError("boom")

    tracer = _FakeTracer()
    monkeypatch.setattr(foundry_main, "get_tracer", lambda _: tracer)
    monkeypatch.setattr(foundry_main, "order_resolution_service", _FailingService())

    with pytest.raises(RuntimeError, match="boom"):
        await foundry_main._run_from_responses(
            {"conversation_id": "C1", "input": "Resolve delayed order ORD-1001"},
            None,
            _FakeTextResponse,
        )

    span = tracer.spans[0]
    assert span.name == "foundry.responses.invoke"
    assert len(span.recorded_exceptions) == 1
    assert isinstance(span.recorded_exceptions[0], RuntimeError)


@pytest.mark.asyncio
async def test_run_from_responses_records_genai_messages_for_trace_evaluation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = _FakeRepository()
    service = _FakeService()
    tracer = _FakeTracer()
    repo.details_by_thread["C1"] = _details(
        thread_id="C1",
        status="completed",
        output_message="Resolution complete.",
    )
    monkeypatch.setenv("TRACE_EVALUATION_RECORD_CONTENT", "true")
    monkeypatch.setattr(foundry_main, "workflow_run_repository", repo)
    monkeypatch.setattr(foundry_main, "order_resolution_service", service)
    monkeypatch.setattr(foundry_main, "get_tracer", lambda _: tracer)

    await foundry_main._run_from_responses(
        {"conversation": {"id": "C1"}, "input": "Resolve delayed order ORD-1001"},
        None,
        _FakeTextResponse,
    )

    span = tracer.spans[0]
    assert json.loads(str(span.attributes["gen_ai.input.messages"])) == [
        {
            "role": "user",
            "parts": [{"type": "text", "content": "Resolve delayed order ORD-1001"}],
        }
    ]
    assert json.loads(str(span.attributes["gen_ai.output.messages"])) == [
        {
            "role": "assistant",
            "parts": [{"type": "text", "content": "Resolution complete."}],
            "finish_reason": "stop",
        }
    ]
