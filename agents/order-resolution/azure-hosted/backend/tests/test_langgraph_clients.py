from __future__ import annotations

import pytest
from app.langgraph import clients


def test_model_config_absent_uses_deterministic_mode() -> None:
    assert clients.get_foundry_models_config() is None
    assert clients.triage_mode_metadata() == {
        "provider": "deterministic",
        "mode": "local_fallback",
    }


def test_model_config_uses_current_foundry_langchain_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "FOUNDRY_PROJECTS_ENDPOINT",
        "https://example.services.ai.azure.com/api/projects/orders",
    )
    monkeypatch.setenv("FOUNDRY_MODEL_DEPLOYMENT_NAME", "gpt-test")

    config = clients.get_foundry_models_config()

    assert config is not None
    assert config.project_endpoint.endswith("/api/projects/orders")
    assert config.model == "gpt-test"
    assert clients.triage_mode_metadata(config) == {
        "provider": "azure_ai",
        "mode": "foundry_models",
        "model": "gpt-test",
    }


@pytest.mark.asyncio
async def test_azure_triage_model_deterministic_fallback() -> None:
    summary, used_model = await clients.AzureTriageModel().summarize(
        message="Order ORD-1009 is late.",
        context_summary="",
    )

    assert used_model is False
    assert summary == "triage_summary: order_id=ord-1009; issue_type=late_delivery"
