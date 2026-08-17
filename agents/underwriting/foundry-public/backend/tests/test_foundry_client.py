from __future__ import annotations

from dataclasses import replace

from app.core.config import Settings
from app.infrastructure.llm import foundry_client


def _settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "db_host": "localhost",
        "db_port": 5432,
        "db_name": "underwriting",
        "db_user": "underwriting",
        "db_password": "underwriting",
        "log_level": "INFO",
        "fail_risk_once": False,
        "fail_credit_randomly": False,
        "crash_after_executor": "",
        "crash_after_step_or_superstep": "",
        "retry_max_attempts": 3,
        "retry_base_delay_ms": 200,
        "retry_jitter_ms": 100,
        "azure_ai_project_id": "",
        "azure_ai_project_name": "",
        "foundry_model_deployment_name": "underwriting-gpt-4-1-mini",
        "azure_openai_endpoint": "https://example.openai.azure.com",
        "azure_openai_api_key": "",
    }
    values.update(overrides)
    return replace(
        Settings(
            db_host="localhost",
            db_port=5432,
            db_name="underwriting",
            db_user="underwriting",
            db_password="underwriting",
            log_level="INFO",
            fail_risk_once=False,
            fail_credit_randomly=False,
            crash_after_executor="",
            crash_after_step_or_superstep="",
            retry_max_attempts=3,
            retry_base_delay_ms=200,
            retry_jitter_ms=100,
            azure_ai_project_id="",
            azure_ai_project_name="",
            foundry_model_deployment_name="underwriting-gpt-4-1-mini",
            azure_openai_endpoint="https://example.openai.azure.com",
            azure_openai_api_key="",
        ),
        **values,
    )


def test_foundry_client_uses_managed_identity_without_api_key(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeCredential:
        pass

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    token_provider = object()
    monkeypatch.setattr(foundry_client, "DefaultAzureCredential", FakeCredential)
    monkeypatch.setattr(
        foundry_client,
        "get_bearer_token_provider",
        lambda credential, scope: token_provider,
    )
    monkeypatch.setattr(foundry_client, "AsyncAzureOpenAI", FakeClient)

    client = foundry_client.FoundryLLMClient(_settings())

    assert isinstance(client._client, FakeClient)
    assert captured["azure_ad_token_provider"] is token_provider
    assert "api_key" not in captured


def test_foundry_client_keeps_local_api_key_support(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeClient:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(foundry_client, "AsyncAzureOpenAI", FakeClient)

    foundry_client.FoundryLLMClient(_settings(azure_openai_api_key="local-key"))

    assert captured["api_key"] == "local-key"
    assert "azure_ad_token_provider" not in captured
