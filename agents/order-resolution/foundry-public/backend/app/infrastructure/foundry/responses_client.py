from __future__ import annotations

import os
from collections.abc import Awaitable, Callable
from typing import Any

import httpx
from azure.identity.aio import DefaultAzureCredential

FOUNDRY_DATA_PLANE_SCOPE = "https://ai.azure.com/.default"


class ResponsesWorkflowClient:
    """Invokes the canonical hosted workflow through its Responses endpoint."""

    def __init__(
        self,
        endpoint: str,
        *,
        timeout_seconds: float = 60,
        transport: Callable[[dict[str, Any]], Awaitable[None]] | None = None,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    @classmethod
    def from_environment(cls) -> ResponsesWorkflowClient:
        endpoint = os.getenv("FOUNDRY_RESPONSES_ENDPOINT", "").strip()
        if not endpoint:
            raise RuntimeError(
                "FOUNDRY_RESPONSES_ENDPOINT is required when RUNTIME_TARGET=responses_wrapper."
            )
        timeout_seconds = float(os.getenv("FOUNDRY_RESPONSES_TIMEOUT_SECONDS", "60"))
        if timeout_seconds <= 0:
            raise ValueError("FOUNDRY_RESPONSES_TIMEOUT_SECONDS must be positive")
        return cls(endpoint, timeout_seconds=timeout_seconds)

    async def start_workflow(self, *, thread_id: str, message: str) -> str:
        if self._is_loopback:
            await self._invoke(
                {
                    "conversation": {"id": thread_id},
                    "input": message,
                }
            )
            return thread_id

        conversation_id = await self._create_conversation()
        await self._invoke(
            {
                "conversation": {"id": conversation_id},
                "input": message,
            }
        )
        return conversation_id

    async def respond_to_hitl(
        self,
        *,
        thread_id: str,
        checkpoint_id: str,
        decision: str,
    ) -> None:
        await self._invoke(
            {
                "conversation": {"id": thread_id},
                "input": [
                    {
                        "type": "function_call_output",
                        "call_id": checkpoint_id,
                        "output": decision,
                    }
                ],
                "stream": not self._is_loopback,
            }
        )

    @property
    def _is_loopback(self) -> bool:
        return self._endpoint.startswith("http://127.0.0.1") or self._endpoint.startswith(
            "http://localhost"
        )

    @property
    def _conversations_endpoint(self) -> str:
        marker = "/responses?"
        if marker not in self._endpoint:
            raise RuntimeError("FOUNDRY_RESPONSES_ENDPOINT must include /responses?api-version=v1.")
        return self._endpoint.replace(marker, "/conversations?", 1)

    async def _create_conversation(self) -> str:
        response = await self._request(self._conversations_endpoint, {})
        body = response.json()
        conversation_id = body.get("id") if isinstance(body, dict) else None
        if not isinstance(conversation_id, str) or not conversation_id.startswith("conv_"):
            raise RuntimeError("Foundry conversation creation returned no valid conversation ID.")
        return conversation_id

    async def _invoke(self, payload: dict[str, Any]) -> None:
        if self._transport is not None:
            await self._transport(payload)
            return
        await self._request(self._endpoint, payload)

    async def _request(self, endpoint: str, payload: dict[str, Any]) -> httpx.Response:
        if self._is_loopback:
            headers: dict[str, str] = {}
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(endpoint, json=payload, headers=headers)
        else:
            async with DefaultAzureCredential(require_envvar=True) as credential:
                token = await credential.get_token(FOUNDRY_DATA_PLANE_SCOPE)
                async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                    response = await client.post(
                        endpoint,
                        json=payload,
                        headers={"Authorization": f"Bearer {token.token}"},
                    )
        response.raise_for_status()
        return response
