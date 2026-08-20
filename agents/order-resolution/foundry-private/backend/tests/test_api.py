from __future__ import annotations

from uuid import uuid4

import pytest
from app.main import app
from app.modules.order_resolution.models import WorkflowEvent
from fastapi.testclient import TestClient

client = TestClient(app)


@pytest.fixture(scope="module", autouse=True)
def app_lifespan():
    with client:
        yield


def test_health_endpoint() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["workflow_mode"] == "langgraph"
    assert isinstance(payload["runtime_provider"], str)
    assert isinstance(payload["runtime_mode"], str)
    assert isinstance(payload["environment"], str)


def test_api_health_endpoint_alias() -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "langgraph-order-resolution-foundry-private-backend"


def test_cors_allows_only_the_configured_frontend_origin() -> None:
    allowed = client.options(
        "/api/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )
    denied = client.options(
        "/api/health",
        headers={
            "Origin": "https://untrusted.example.test",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-origin" not in denied.headers


def test_copilotkit_discovery_is_static_and_redacted() -> None:
    response = client.get("/api/copilotkit")
    info_response = client.get("/api/copilotkit/info")

    assert response.status_code == 200
    assert info_response.status_code == 200
    expected_discovery = {
        "version": "1.0",
        "agents": {
            "order-resolution-thread-assistant": {
                "name": "Order Resolution Thread Assistant",
                "className": "OrderResolutionThreadAssistant",
                "description": (
                    "Provides a read-only, redacted durable-event view for a selected workflow "
                    "thread."
                ),
            }
        },
        "audioFileTranscriptionEnabled": False,
        "mode": "sse",
        "threadEndpoints": {
            "list": False,
            "inspect": False,
            "mutations": False,
            "realtimeMetadata": False,
        },
        "a2uiEnabled": False,
    }
    assert response.json() == expected_discovery
    assert info_response.json() == expected_discovery
    serialized = response.text.lower()
    assert "ord-1009" not in serialized
    assert "credential" not in serialized
    assert "checkpoint" not in serialized
    assert "prompt" not in serialized


def test_chat_run_starts_workflow() -> None:
    response = client.post(
        "/api/chat/run",
        json={"message": "Order ORD-1009 is delayed by 5 days."},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["thread_id"]


def test_chat_run_rejects_new_message_on_interrupted_thread() -> None:
    thread_id = str(uuid4())
    first = client.post(
        "/api/chat/run",
        json={
            "thread_id": thread_id,
            "message": "Order ORD-1009 is delayed by five days.",
        },
    )
    assert first.status_code == 200

    blocked = client.post(
        "/api/chat/run",
        json={
            "thread_id": thread_id,
            "message": "Start a new normal request instead.",
        },
    )

    assert blocked.status_code == 409
    details = client.get(f"/api/workflows/{thread_id}").json()
    checkpoint_id = details["pending_approvals"][0]["checkpoint_id"]
    client.post(
        "/api/hitl/respond",
        json={
            "checkpoint_id": checkpoint_id,
            "decision": "reject",
            "reviewer": "api-test",
        },
    )


def test_workflow_list_accepts_both_page_size_params() -> None:
    response = client.get("/api/workflows?page=1&page_size=5")
    assert response.status_code == 200
    assert response.json()["page_size"] == 5

    legacy_response = client.get("/api/workflows?page=1&pageSize=3")
    assert legacy_response.status_code == 200
    assert legacy_response.json()["page_size"] == 3


def test_workflow_events_endpoint_is_cursor_paginated() -> None:
    run = client.post(
        "/api/chat/run",
        json={"message": "Order ORD-1001 arrived a day late."},
    )
    assert run.status_code == 200
    thread_id = run.json()["thread_id"]

    events_response = client.get(f"/api/workflows/{thread_id}/events?limit=2")
    assert events_response.status_code == 200
    payload = events_response.json()
    assert "items" in payload
    assert "pagination" in payload
    assert payload["pagination"]["limit"] == 2
    assert isinstance(payload["pagination"]["has_more"], bool)
    assert len(payload["items"]) <= 2

    event_types = {item["type"] for item in payload["items"]}
    assert "workflow.stage" in event_types or payload["pagination"]["has_more"]


def test_workflow_events_endpoint_rejects_invalid_cursor() -> None:
    run = client.post(
        "/api/chat/run",
        json={"message": "Order ORD-1001 arrived a day late."},
    )
    assert run.status_code == 200
    thread_id = run.json()["thread_id"]

    response = client.get(f"/api/workflows/{thread_id}/events?limit=2&cursor=invalid-cursor")
    assert response.status_code == 400


def test_workflow_events_endpoint_rejects_malformed_structured_cursor() -> None:
    run = client.post(
        "/api/chat/run",
        json={"message": "Order ORD-1001 arrived a day late."},
    )
    assert run.status_code == 200
    thread_id = run.json()["thread_id"]

    response = client.get(
        f"/api/workflows/{thread_id}/events?limit=2&cursor=not-a-timestamp|not-a-uuid"
    )
    assert response.status_code == 400


def test_workflow_events_endpoint_cursor_advances_without_overlap() -> None:
    run = client.post(
        "/api/chat/run",
        json={"message": "Order ORD-1001 arrived a day late."},
    )
    assert run.status_code == 200
    thread_id = run.json()["thread_id"]

    first_page = client.get(f"/api/workflows/{thread_id}/events?limit=1")
    assert first_page.status_code == 200
    first_payload = first_page.json()
    assert len(first_payload["items"]) == 1

    first_cursor = first_payload["pagination"]["next_cursor"]
    assert first_cursor is not None

    second_page = client.get(
        f"/api/workflows/{thread_id}/events",
        params={"limit": 1, "cursor": first_cursor},
    )
    assert second_page.status_code == 200
    second_payload = second_page.json()
    assert len(second_payload["items"]) == 1
    assert second_payload["items"][0]["id"] != first_payload["items"][0]["id"]


def test_session_messages_endpoint_supports_cursor_pagination() -> None:
    session_id = f"session-{uuid4()}"
    run = client.post(
        "/api/chat/run",
        json={
            "message": "Order ORD-1001 arrived a day late.",
            "session_id": session_id,
        },
    )
    assert run.status_code == 200

    first_page = client.get(f"/api/sessions/{session_id}/messages?limit=1")
    assert first_page.status_code == 200
    payload = first_page.json()
    assert len(payload["items"]) == 1
    assert payload["pagination"]["limit"] == 1
    assert payload["items"][0]["session_id"] == session_id

    next_cursor = payload["pagination"]["next_cursor"]
    assert next_cursor is not None

    second_page = client.get(f"/api/sessions/{session_id}/messages?limit=1&cursor={next_cursor}")
    assert second_page.status_code == 200
    second_payload = second_page.json()
    assert len(second_payload["items"]) >= 1
    assert int(second_payload["items"][0]["id"]) > int(next_cursor)


def test_session_messages_endpoint_returns_empty_page_after_last_cursor() -> None:
    session_id = f"session-{uuid4()}"
    run = client.post(
        "/api/chat/run",
        json={
            "message": "Order ORD-1001 arrived a day late.",
            "session_id": session_id,
        },
    )
    assert run.status_code == 200

    response = client.get(f"/api/sessions/{session_id}/messages?limit=2&cursor=999999")
    assert response.status_code == 200
    payload = response.json()
    assert payload["items"] == []
    assert payload["pagination"]["has_more"] is False
    assert payload["pagination"]["next_cursor"] is None


@pytest.mark.asyncio
async def test_native_sse_stream_replays_durable_events_even_in_local_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api.v1.routers import chat as chat_router

    event = WorkflowEvent(
        id=str(uuid4()),
        type="workflow.stage",
        thread_id="thread-durable-sse",
        payload={"agent": "triage", "status": "completed"},
    )

    def read_page(thread_id: str, limit: int, cursor: str | None):
        assert thread_id == "thread-durable-sse"
        assert limit == 100
        return ([event], None, False) if cursor is None else ([], None, False)

    monkeypatch.setattr(chat_router.workflow_run_repository, "list_workflow_events", read_page)

    response = await chat_router.stream_chat("thread-durable-sse")
    first_frame = await anext(response.body_iterator)

    assert "workflow.stage" in first_frame
    assert event.id in first_frame
