from __future__ import annotations

import hashlib
import json
from uuid import NAMESPACE_URL, uuid4, uuid5

from app.api.v1.schemas.chat import ChatRunRequest, ChatRunResponse
from app.api.v1.schemas.hitl import HitlResponseRequest, HitlResponseResult
from app.modules.order_resolution.models import PendingApprovalError, WorkflowContext
from app.modules.order_resolution.ports import (
    WorkflowEngine,
    WorkflowRunRepositoryPort,
)


class OrderResolutionService:
    def __init__(
        self,
        *,
        workflow: WorkflowEngine,
        workflow_run_repository: WorkflowRunRepositoryPort,
    ) -> None:
        self._workflow = workflow
        self._workflow_run_repository = workflow_run_repository

    async def startup(self) -> None:
        await self._workflow.startup()

    async def shutdown(self) -> None:
        await self._workflow.shutdown()

    async def start_chat_run(self, request: ChatRunRequest) -> ChatRunResponse:
        idempotency_key = request.idempotency_key
        run_id = (
            str(
                uuid5(
                    NAMESPACE_URL,
                    f"order-resolution:run:{idempotency_key}",
                )
            )
            if idempotency_key
            else str(uuid4())
        )
        thread_id = request.thread_id or (
            str(
                uuid5(
                    NAMESPACE_URL,
                    f"order-resolution:thread:{idempotency_key}",
                )
            )
            if idempotency_key
            else str(uuid4())
        )
        session_id = request.session_id or thread_id
        request_hash = self._request_hash(
            request=request,
            thread_id=thread_id,
            session_id=session_id,
        )

        dispatch: dict[str, object] | None = None
        if idempotency_key:
            dispatch = self._workflow_run_repository.create_or_get_responses_dispatch(
                idempotency_key=idempotency_key,
                request_hash=request_hash,
                run_id=run_id,
                thread_id=thread_id,
            )
            run_id = str(dispatch["run_id"])
            thread_id = str(dispatch["thread_id"])
            session_id = request.session_id or thread_id
            dispatch_status = str(dispatch["status"])
            if not dispatch.get("created", False) and dispatch_status in {
                "pending",
                "running",
                "submitted",
            }:
                return ChatRunResponse(run_id=run_id, thread_id=thread_id)
            if dispatch_status == "blocked_pending_approval":
                await self._workflow.assert_thread_can_start(thread_id)

        context = WorkflowContext(
            run_id=run_id,
            thread_id=thread_id,
            session_id=session_id,
            customer_id=request.customer_id,
            user_message=request.message,
        )
        self._workflow_run_repository.create_workflow_run(
            thread_id=thread_id,
            input_text=request.message,
            session_id=session_id,
            customer_id=request.customer_id,
        )
        if idempotency_key:
            self._workflow_run_repository.update_responses_dispatch_status(
                idempotency_key, "running"
            )
        try:
            await self._workflow.start(context)
        except PendingApprovalError:
            if idempotency_key:
                self._workflow_run_repository.update_responses_dispatch_status(
                    idempotency_key, "blocked_pending_approval"
                )
            raise
        except Exception:
            if idempotency_key:
                self._workflow_run_repository.update_responses_dispatch_status(
                    idempotency_key, "unknown"
                )
            raise
        if idempotency_key:
            self._workflow_run_repository.update_responses_dispatch_status(
                idempotency_key, "submitted"
            )

        return ChatRunResponse(run_id=run_id, thread_id=thread_id)

    @staticmethod
    def _request_hash(
        *,
        request: ChatRunRequest,
        thread_id: str,
        session_id: str,
    ) -> str:
        return hashlib.sha256(
            json.dumps(
                {
                    "message": request.message,
                    "thread_id": thread_id,
                    "session_id": session_id,
                    "customer_id": request.customer_id,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()

    async def respond_hitl(self, request: HitlResponseRequest) -> HitlResponseResult:
        thread_id = await self._workflow.handle_hitl_response(
            checkpoint_id=request.checkpoint_id,
            decision=request.decision,
            reviewer=request.reviewer,
            comments=request.comments,
        )
        return HitlResponseResult(
            accepted=True,
            checkpoint_id=request.checkpoint_id,
            thread_id=thread_id,
        )
