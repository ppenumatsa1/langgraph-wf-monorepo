from __future__ import annotations

from pathlib import Path

import pytest
from app.core.config import get_config


@pytest.fixture(autouse=True)
def clear_config_cache():
    get_config.cache_clear()
    yield
    get_config.cache_clear()


def test_config_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STORE_PROVIDER", raising=False)
    monkeypatch.delenv("DEPLOYMENT_LANE", raising=False)

    cfg = get_config()
    assert cfg.workflow_mode == "langgraph"
    assert cfg.store_provider == "postgres"
    assert cfg.runtime_target == "local_langgraph"
    assert cfg.deployment_lane == "foundry-private"


def test_config_uses_store_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORE_PROVIDER", "azure_postgres")

    cfg = get_config()
    assert cfg.workflow_mode == "langgraph"
    assert cfg.store_provider == "azure_postgres"


def test_config_selects_responses_wrapper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUNTIME_TARGET", "responses_wrapper")

    assert get_config().runtime_target == "responses_wrapper"


def test_config_rejects_non_private_lane(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEPLOYMENT_LANE", "foundry-public")

    with pytest.raises(ValueError, match="Unsupported DEPLOYMENT_LANE"):
        get_config()


def test_docker_images_declare_private_runtime_metadata() -> None:
    backend_root = Path(__file__).parents[1]
    wrapper = (backend_root / "Dockerfile").read_text(encoding="utf-8")
    hosted = (backend_root / "Dockerfile.hosted").read_text(encoding="utf-8")

    assert 'com.microsoft.langgraph.deployment-lane="foundry-private"' in wrapper
    assert "RUNTIME_TARGET=responses_wrapper" in wrapper
    assert 'com.microsoft.langgraph.deployment-lane="foundry-private"' in hosted
    assert "RUNTIME_TARGET=local_langgraph" in hosted


def test_config_validates_checkpoint_retention(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHECKPOINT_RETENTION_DAYS", "30")

    assert get_config().checkpoint_retention_days == 30

    get_config.cache_clear()
    monkeypatch.setenv("CHECKPOINT_RETENTION_DAYS", "0")
    with pytest.raises(ValueError, match="positive integer"):
        get_config()
