from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Literal

WorkflowMode = Literal["langgraph"]
StoreProvider = Literal["postgres", "azure_postgres", "app_db"]
RuntimeTarget = Literal["local_langgraph", "responses_wrapper"]
DeploymentLane = Literal["foundry-private"]


@dataclass(frozen=True)
class AppConfig:
    workflow_mode: WorkflowMode
    store_provider: StoreProvider
    runtime_target: RuntimeTarget = "local_langgraph"
    deployment_lane: DeploymentLane = "foundry-private"
    checkpoint_retention_days: int | None = None


def _normalized(name: str, default: str) -> str:
    return (os.getenv(name, default) or default).strip().lower()


def _store_provider() -> StoreProvider:
    value = _normalized("STORE_PROVIDER", "postgres")
    if value in {"postgres", "azure_postgres", "app_db"}:
        return value
    raise ValueError(f"Unsupported STORE_PROVIDER: {value}")


def _runtime_target() -> RuntimeTarget:
    value = _normalized("RUNTIME_TARGET", "local_langgraph")
    if value in {"local_langgraph", "responses_wrapper"}:
        return value
    raise ValueError(f"Unsupported RUNTIME_TARGET: {value}")


def _deployment_lane() -> DeploymentLane:
    value = _normalized("DEPLOYMENT_LANE", "foundry-private")
    if value == "foundry-private":
        return value
    raise ValueError(f"Unsupported DEPLOYMENT_LANE: {value}")


def _checkpoint_retention_days() -> int | None:
    raw = os.getenv("CHECKPOINT_RETENTION_DAYS", "").strip()
    if not raw:
        return None
    value = int(raw)
    if value < 1:
        raise ValueError("CHECKPOINT_RETENTION_DAYS must be a positive integer.")
    return value


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    return AppConfig(
        workflow_mode="langgraph",
        store_provider=_store_provider(),
        runtime_target=_runtime_target(),
        deployment_lane=_deployment_lane(),
        checkpoint_retention_days=_checkpoint_retention_days(),
    )
