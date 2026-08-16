from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from app.api.v1.schemas.chat import ChatRunRequest
from app.infrastructure.persistence import WorkflowRunRepository
from app.modules.order_resolution.service import OrderResolutionService


class _NoopWorkflow:
    async def startup(self) -> None:
        return None

    async def shutdown(self) -> None:
        return None

    async def assert_thread_can_start(self, thread_id: str) -> None:
        return None

    async def start(self, context: object) -> None:
        return None

    async def handle_hitl_response(self, **_: object) -> str:
        return "thread-unused"


class _CountingResponsesClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def start_workflow(self, *, thread_id: str, message: str) -> str:
        self.calls.append((thread_id, message))
        await asyncio.sleep(0.05)
        return thread_id

    async def respond_to_hitl(
        self,
        *,
        thread_id: str,
        checkpoint_id: str,
        decision: str,
    ) -> None:
        return None


@pytest.mark.asyncio
async def test_responses_retry_is_idempotent_under_concurrent_same_thread_replays() -> None:
    repository = WorkflowRunRepository()
    responses_client = _CountingResponsesClient()
    service = OrderResolutionService(
        workflow=_NoopWorkflow(),
        workflow_run_repository=repository,
        responses_client=responses_client,
    )
    thread_id = str(uuid4())
    idempotency_key = str(uuid4())
    request = ChatRunRequest(
        thread_id=thread_id,
        message="Order ORD-1009 is delayed by 5 days.",
        idempotency_key=idempotency_key,
    )

    first, second = await asyncio.gather(
        service.start_chat_run(request),
        service.start_chat_run(request.model_copy()),
    )

    assert first.thread_id == thread_id
    assert second.thread_id == thread_id
    assert first.run_id == second.run_id
    assert responses_client.calls == [(thread_id, request.message)]
