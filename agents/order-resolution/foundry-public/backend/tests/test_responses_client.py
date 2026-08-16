from __future__ import annotations

from typing import Any

import pytest
from app.infrastructure.foundry import responses_client
from app.infrastructure.foundry.responses_client import ResponsesWorkflowClient


@pytest.mark.asyncio
async def test_responses_client_maps_new_workflow_to_conversation() -> None:
    payloads: list[dict[str, Any]] = []

    async def capture(payload: dict[str, Any]) -> None:
        payloads.append(payload)

    client = ResponsesWorkflowClient("http://127.0.0.1:8088", transport=capture)
    await client.start_workflow(thread_id="thread-1", message="Resolve ORD-1001")

    assert payloads == [
        {
            "conversation": {"id": "thread-1"},
            "input": "Resolve ORD-1001",
        }
    ]


@pytest.mark.asyncio
async def test_responses_client_preserves_checkpoint_resume_wire_format() -> None:
    payloads: list[dict[str, Any]] = []

    async def capture(payload: dict[str, Any]) -> None:
        payloads.append(payload)

    client = ResponsesWorkflowClient("http://127.0.0.1:8088", transport=capture)
    await client.respond_to_hitl(
        thread_id="thread-1",
        checkpoint_id="checkpoint-1",
        decision="approve",
    )

    assert payloads[0]["conversation"] == {"id": "thread-1"}
    assert payloads[0]["input"] == [
        {
            "type": "function_call_output",
            "call_id": "checkpoint-1",
            "output": "approve",
        }
    ]


@pytest.mark.asyncio
async def test_responses_client_sends_managed_identity_bearer_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_headers: dict[str, str] = {}

    class FakeToken:
        token = "managed-identity-token"

    class FakeCredential:
        def __init__(self, *, require_envvar: bool) -> None:
            assert require_envvar is True

        async def __aenter__(self) -> FakeCredential:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def get_token(self, scope: str) -> FakeToken:
            assert scope == responses_client.FOUNDRY_DATA_PLANE_SCOPE
            return FakeToken()

    class FakeResponse:
        def __init__(self, body: dict[str, str]) -> None:
            self._body = body

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, str]:
            return self._body

    class FakeHttpClient:
        def __init__(self, *, timeout: float) -> None:
            assert timeout == 60

        async def __aenter__(self) -> FakeHttpClient:
            return self

        async def __aexit__(self, *_args: object) -> None:
            return None

        async def post(
            self, endpoint: str, *, json: dict[str, Any], headers: dict[str, str]
        ) -> FakeResponse:
            captured_headers.update(headers)
            if "/conversations?" in endpoint:
                assert json == {}
                return FakeResponse({"id": "conv_managed_identity"})
            assert json["input"] == "Resolve ORD-1001"
            assert json["conversation"] == {"id": "conv_managed_identity"}
            assert "stream" not in json
            return FakeResponse({})

    monkeypatch.setattr(responses_client, "DefaultAzureCredential", FakeCredential)
    monkeypatch.setattr(responses_client.httpx, "AsyncClient", FakeHttpClient)

    client = ResponsesWorkflowClient(
        "https://example.services.ai.azure.com/responses?api-version=v1"
    )
    await client.start_workflow(thread_id="thread-1", message="Resolve ORD-1001")

    assert captured_headers == {"Authorization": "Bearer managed-identity-token"}
