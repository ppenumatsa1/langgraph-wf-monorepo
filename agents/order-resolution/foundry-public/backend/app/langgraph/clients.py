from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol

from app.langgraph.prompts import TRIAGE_INSTRUCTIONS
from app.langgraph.tools import deterministic_triage_summary


@dataclass(frozen=True)
class FoundryModelsConfig:
    project_endpoint: str
    model: str
    provider: str = "azure_ai"


class TriageModel(Protocol):
    async def summarize(self, *, message: str, context_summary: str) -> tuple[str, bool]: ...


def _env(name: str) -> str | None:
    value = os.getenv(name)
    if value is None:
        return None
    return value.strip() or None


def disable_langsmith_tracing() -> None:
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"


def get_foundry_models_config() -> FoundryModelsConfig | None:
    project_endpoint = _env("FOUNDRY_PROJECTS_ENDPOINT") or _env("FOUNDRY_PROJECT_ENDPOINT")
    model = _env("FOUNDRY_MODEL_DEPLOYMENT_NAME") or _env("FOUNDRY_MODEL")
    if not project_endpoint or not model:
        return None
    return FoundryModelsConfig(project_endpoint=project_endpoint, model=model)


def has_llm_configuration() -> bool:
    return get_foundry_models_config() is not None


def triage_mode_metadata(
    config: FoundryModelsConfig | None = None,
) -> dict[str, str]:
    resolved = config if config is not None else get_foundry_models_config()
    if resolved is None:
        return {"provider": "deterministic", "mode": "local_fallback"}
    return {
        "provider": resolved.provider,
        "mode": "foundry_models",
        "model": resolved.model,
    }


class AzureTriageModel:
    async def summarize(self, *, message: str, context_summary: str) -> tuple[str, bool]:
        disable_langsmith_tracing()
        config = get_foundry_models_config()
        if config is None:
            return f"triage_summary: {deterministic_triage_summary(message)}", False

        from azure.identity.aio import DefaultAzureCredential
        from langchain_azure_ai.chat_models import AzureAIOpenAIApiChatModel
        from langchain_core.messages import HumanMessage, SystemMessage

        credential = DefaultAzureCredential()
        model = AzureAIOpenAIApiChatModel(
            project_endpoint=config.project_endpoint,
            credential=credential,
            model=config.model,
            temperature=0,
            store=False,
        )
        try:
            response = await model.ainvoke(
                [
                    SystemMessage(content=TRIAGE_INSTRUCTIONS),
                    HumanMessage(content=f"context:\n{context_summary}\n\nrequest:\n{message}"),
                ]
            )
            return self._response_text(response), True
        finally:
            await credential.close()

    @staticmethod
    def _response_text(response: Any) -> str:
        text = getattr(response, "text", None)
        if isinstance(text, str) and text.strip():
            return text.strip()
        content = getattr(response, "content", response)
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    value = item.get("text") or item.get("content")
                    if isinstance(value, str):
                        parts.append(value)
            return " ".join(parts).strip()
        return str(content).strip()
