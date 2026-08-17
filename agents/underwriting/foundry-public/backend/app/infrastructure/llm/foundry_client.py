from __future__ import annotations

import json
import logging

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AsyncAzureOpenAI

from app.core.config import Settings
from app.modules.underwriting.models import Decision

logger = logging.getLogger(__name__)
_cognitive_services_scope = "https://cognitiveservices.azure.com/.default"


class FoundryLLMClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._client: AsyncAzureOpenAI | None = None
        if settings.azure_openai_endpoint and settings.foundry_model_deployment_name:
            if settings.azure_openai_api_key:
                self._client = AsyncAzureOpenAI(
                    api_key=settings.azure_openai_api_key,
                    azure_endpoint=settings.azure_openai_endpoint,
                    api_version="2024-10-21",
                )
            else:
                self._client = AsyncAzureOpenAI(
                    azure_ad_token_provider=get_bearer_token_provider(
                        DefaultAzureCredential(), _cognitive_services_scope
                    ),
                    azure_endpoint=settings.azure_openai_endpoint,
                    api_version="2024-10-21",
                )

    async def generate_rationale(
        self,
        *,
        decision: Decision,
        average_score: float,
        score_breakdown: dict[str, float],
    ) -> str:
        if self._client is None:
            logger.info(
                "foundry_client_fallback project_id=%s project_name=%s deployment=%s",
                self.settings.azure_ai_project_id or "-",
                self.settings.azure_ai_project_name or "-",
                self.settings.foundry_model_deployment_name or "-",
            )
            return f"Decision based on average check score {average_score:.3f}"

        prompt = (
            "You are an underwriting assistant. Return a concise 1-2 sentence rationale.\n"
            f"Decision: {decision.value}\n"
            f"Average score: {average_score:.3f}\n"
            f"Score breakdown: {json.dumps(score_breakdown, sort_keys=True)}"
        )
        response = await self._client.chat.completions.create(
            model=self.settings.foundry_model_deployment_name,
            messages=[
                {"role": "system", "content": "Generate concise underwriting rationale."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=120,
        )
        content = response.choices[0].message.content if response.choices else None
        return (
            content.strip()
            if content
            else f"Decision based on average check score {average_score:.3f}"
        )
