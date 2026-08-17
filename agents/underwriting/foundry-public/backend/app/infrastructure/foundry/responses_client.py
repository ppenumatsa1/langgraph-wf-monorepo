from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import OpenAI

from app.core.config import Settings
from app.modules.underwriting.copilot import SafeRunExplanationRequest
from app.modules.underwriting.hosted import HostedWorkflowEnvelope

_FOUNDRY_SCOPE = "https://ai.azure.com/.default"


class UnderwritingResponsesClient:
    """Server-side client for the canonical hosted underwriting workflow."""

    def __init__(self, settings: Settings):
        self._settings = settings

    async def invoke(
        self, request_envelope: HostedWorkflowEnvelope | SafeRunExplanationRequest
    ) -> dict[str, Any]:
        return await asyncio.to_thread(self._invoke, request_envelope)

    def _invoke(
        self, request_envelope: HostedWorkflowEnvelope | SafeRunExplanationRequest
    ) -> dict[str, Any]:
        request = request_envelope.to_dict()
        response = self._invoke_responses(request)
        output_text = getattr(response, "output_text", None)
        if not isinstance(output_text, str) or not output_text.strip():
            raise RuntimeError("Foundry hosted agent returned an empty response.")
        try:
            payload = json.loads(output_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError("Foundry hosted agent returned an invalid response.") from exc
        if not isinstance(payload, dict):
            raise RuntimeError("Foundry hosted agent returned a non-object response.")
        if payload.get("workflow_run_id") != request_envelope.workflow_run_id:
            raise RuntimeError("Foundry hosted agent returned an unexpected workflow_run_id.")
        return payload

    def _invoke_responses(self, request: dict[str, Any]) -> Any:
        if self._settings.foundry_responses_timeout_seconds <= 0:
            raise ValueError("FOUNDRY_RESPONSES_TIMEOUT_SECONDS must be positive")
        endpoint = self._settings.foundry_responses_endpoint.strip()
        if endpoint:
            base_url, default_query = _responses_endpoint_config(endpoint)
            credential = DefaultAzureCredential(
                managed_identity_client_id=self._settings.azure_client_id or None
            )
            client = OpenAI(
                api_key=get_bearer_token_provider(credential, _FOUNDRY_SCOPE),
                base_url=base_url,
                default_query=default_query,
                timeout=self._settings.foundry_responses_timeout_seconds,
            )
            try:
                return self._create_response(client, request)
            finally:
                _close(client)
                _close(credential)

        if self._settings.foundry_hosted_agent_version:
            raise RuntimeError(
                "FOUNDRY_RESPONSES_ENDPOINT is required to invoke a pinned hosted-agent version."
            )
        project_endpoint = self._settings.azure_ai_project_endpoint.strip()
        if not project_endpoint:
            raise RuntimeError(
                "AZURE_AI_PROJECT_ENDPOINT or FOUNDRY_RESPONSES_ENDPOINT is required for hosted runs."
            )
        with AIProjectClient(
            endpoint=project_endpoint,
            credential=DefaultAzureCredential(
                managed_identity_client_id=self._settings.azure_client_id or None
            ),
            allow_preview=True,
        ) as project:
            client = project.get_openai_client(agent_name=self._settings.foundry_hosted_agent_name)
            try:
                return self._create_response(client, request)
            finally:
                _close(client)

    def _create_response(self, client: Any, request: dict[str, Any]) -> Any:
        return client.responses.create(
            input=[
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": json.dumps(request)}],
                }
            ],
            metadata={
                "protocol": request["protocol"],
                "workflow_run_id": request["workflow_run_id"],
                "action": request.get("action", "explain"),
                "hosted_agent_version": self._settings.foundry_hosted_agent_version,
            },
        )


def _responses_endpoint_config(endpoint: str) -> tuple[str, dict[str, str]]:
    parsed = urlsplit(endpoint)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("FOUNDRY_RESPONSES_ENDPOINT must be an absolute URL.")
    path = parsed.path.rstrip("/")
    if path.endswith("/responses"):
        path = path[: -len("/responses")]
    if not path.endswith("/protocols/openai"):
        raise ValueError(
            "FOUNDRY_RESPONSES_ENDPOINT must target a hosted agent OpenAI Responses endpoint."
        )
    return (
        urlunsplit((parsed.scheme, parsed.netloc, f"{path}/", "", "")),
        dict(parse_qsl(parsed.query, keep_blank_values=True)),
    )


def _close(value: Any) -> None:
    close = getattr(value, "close", None)
    if callable(close):
        close()
