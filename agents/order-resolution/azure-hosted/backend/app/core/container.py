from __future__ import annotations

import os

from app.core.config import get_config
from app.core.database import postgres_db
from app.core.telemetry import record_workflow_event
from app.infrastructure.events import EventBus
from app.infrastructure.mcp import MCPKnowledgeTool
from app.infrastructure.persistence import (
    CheckpointStore,
    IdempotencyStore,
    PostgresSessionMemoryStore,
    WorkflowRunRepository,
)
from app.infrastructure.rag.providers.noop_provider import NoopRAGProvider
from app.langgraph import (
    AzureTriageModel,
    LangGraphOrderResolutionWorkflow,
    PostgresCheckpointerFactory,
    disable_langsmith_tracing,
)
from app.langgraph.nodes import NodeDependencies
from app.modules.order_resolution.projections import WorkflowRunEventProjector
from app.modules.order_resolution.service import OrderResolutionService

config = get_config()
disable_langsmith_tracing()
if config.store_provider != "postgres":
    raise RuntimeError(
        "Store provider switching is not implemented yet. Use STORE_PROVIDER=postgres."
    )
if os.getenv("VERIFY_DB_SCHEMA_ON_STARTUP", "true").strip().lower() in {
    "1",
    "true",
    "yes",
}:
    postgres_db.verify_runtime_schema()

event_bus = EventBus()
workflow_run_repository = WorkflowRunRepository()
memory_store = PostgresSessionMemoryStore()
checkpoint_store = CheckpointStore()
idempotency_store = IdempotencyStore()
mcp_tool = MCPKnowledgeTool()
rag_provider = NoopRAGProvider()
checkpointer_factory = PostgresCheckpointerFactory(postgres_db.database_url)
workflow_run_event_projector = WorkflowRunEventProjector(workflow_run_repository)

event_bus.add_listener(workflow_run_event_projector.sync_event_to_run)
event_bus.add_listener(record_workflow_event)

workflow = LangGraphOrderResolutionWorkflow(
    event_bus=event_bus,
    memory_store=memory_store,
    interrupt_repository=checkpoint_store,
    workflow_run_repository=workflow_run_repository,
    checkpointer_factory=checkpointer_factory,
    node_dependencies=NodeDependencies(
        triage_model=AzureTriageModel(),
        rag_provider=rag_provider,
        mcp_tool=mcp_tool,
        idempotency_store=idempotency_store,
        retry_attempts=max(1, int(os.getenv("READ_RETRY_ATTEMPTS", "3"))),
        retry_delay_seconds=max(0.0, float(os.getenv("READ_RETRY_DELAY_SECONDS", "0.2"))),
    ),
)

order_resolution_service = OrderResolutionService(
    workflow=workflow,
    workflow_run_repository=workflow_run_repository,
)
