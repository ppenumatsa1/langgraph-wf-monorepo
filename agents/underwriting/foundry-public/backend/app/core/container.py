from __future__ import annotations

import os
from functools import lru_cache

from app.core.config import Settings, load_settings
from app.core.database import postgres_db
from app.infrastructure.foundry.responses_client import UnderwritingResponsesClient
from app.infrastructure.llm.foundry_client import FoundryLLMClient
from app.infrastructure.persistence.idempotency_store import IdempotencyStore
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository
from app.langgraph import LangGraphUnderwritingRunner, PostgresCheckpointerFactory
from app.langgraph.nodes import NodeDependencies
from app.modules.underwriting.copilot_bridge import UnderwritingCopilotBridge
from app.modules.underwriting.ports import UnderwritingHostedWorkflowPort
from app.modules.underwriting.service import UnderwritingService


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()


def _verify_runtime_schema() -> None:
    if os.getenv("VERIFY_DB_SCHEMA_ON_STARTUP", "true").strip().lower() in {"1", "true", "yes"}:
        postgres_db.verify_runtime_schema()


def build_underwriting_service(
    settings: Settings,
    *,
    responses_client: UnderwritingHostedWorkflowPort | None = None,
) -> UnderwritingService:
    if settings.execution_mode not in {"hosted", "local"}:
        raise ValueError("UNDERWRITING_EXECUTION_MODE must be 'hosted' or 'local'")

    _verify_runtime_schema()
    repository = WorkflowRunRepository()
    workflow = (
        LangGraphUnderwritingRunner(
            repository=repository,
            checkpointer_factory=PostgresCheckpointerFactory(
                postgres_db.database_url,
                repository,
            ),
            node_dependencies=NodeDependencies(
                repository=repository,
                idempotency_store=IdempotencyStore(),
                settings=settings,
                llm_client=FoundryLLMClient(settings),
            ),
        )
        if settings.execution_mode == "local"
        else None
    )
    effective_responses_client = (
        responses_client
        if responses_client is not None
        else (
            UnderwritingResponsesClient(settings) if settings.execution_mode == "hosted" else None
        )
    )
    return UnderwritingService(
        settings=settings,
        workflow=workflow,
        workflow_run_repository=repository,
        responses_client=effective_responses_client,
    )


@lru_cache(maxsize=1)
def get_underwriting_service() -> UnderwritingService:
    return build_underwriting_service(get_settings())


@lru_cache(maxsize=1)
def get_copilot_bridge() -> UnderwritingCopilotBridge:
    service = get_underwriting_service()
    return UnderwritingCopilotBridge(
        get_settings(),
        repository=service.repository,
        responses_client=service.responses_client,
    )
