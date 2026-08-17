from __future__ import annotations

import asyncio
from typing import Any

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.core.telemetry import workflow_stage_span
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository


class TracingAsyncPostgresSaver(AsyncPostgresSaver):
    def __init__(
        self,
        conn: Any,
        repository: WorkflowRunRepository,
        *,
        pipe: Any = None,
        serde: Any = None,
    ) -> None:
        super().__init__(conn, pipe=pipe, serde=serde)
        self._repository = repository

    async def aget_tuple(self, config: dict[str, Any]) -> Any:
        configurable = config.get("configurable", {})
        attributes = {
            "workflow.run_id": configurable.get("thread_id"),
            "workflow.checkpoint_id": configurable.get("checkpoint_id"),
            "workflow.executor": "checkpoint_storage",
        }
        with workflow_stage_span("checkpoint.load", attributes):
            return await super().aget_tuple(config)

    async def aput(
        self,
        config: dict[str, Any],
        checkpoint: Any,
        metadata: Any,
        new_versions: Any,
    ) -> dict[str, Any]:
        configurable = config.get("configurable", {})
        attributes = {
            "workflow.run_id": configurable.get("thread_id"),
            "workflow.checkpoint_id": configurable.get("checkpoint_id"),
            "workflow.executor": "checkpoint_storage",
        }
        with workflow_stage_span("checkpoint.save", attributes):
            updated = await super().aput(config, checkpoint, metadata, new_versions)
            updated_configurable = updated.get("configurable", {})
            await asyncio.to_thread(
                self._repository.record_checkpoint,
                workflow_run_id=str(
                    updated_configurable.get("thread_id") or configurable.get("thread_id")
                ),
                checkpoint_id=str(
                    updated_configurable.get("checkpoint_id") or checkpoint.get("id") or ""
                ),
                checkpoint_ns=str(updated_configurable.get("checkpoint_ns") or ""),
                parent_checkpoint_id=(
                    str(configurable.get("checkpoint_id"))
                    if configurable.get("checkpoint_id") is not None
                    else None
                ),
                metadata_json=metadata if isinstance(metadata, dict) else {},
            )
            return updated
