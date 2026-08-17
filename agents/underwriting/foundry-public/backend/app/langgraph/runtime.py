from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from app.core.telemetry import workflow_stage_span
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository
from app.langgraph.checkpointer import CheckpointerFactory
from app.langgraph.factory import GRAPH_NAME, build_underwriting_graph
from app.langgraph.nodes import NodeDependencies
from app.modules.underwriting.ports import WorkflowRunAlreadyClaimedError


@dataclass(frozen=True)
class WorkflowContext:
    workflow_run_id: str
    application: dict[str, Any]


class LangGraphUnderwritingRunner:
    def __init__(
        self,
        repository: WorkflowRunRepository,
        checkpointer_factory: CheckpointerFactory,
        node_dependencies: NodeDependencies,
    ) -> None:
        self._repository = repository
        self._checkpointer_factory = checkpointer_factory
        self._node_dependencies = node_dependencies
        self._graph: Any | None = None
        self._lock = asyncio.Lock()

    async def startup(self) -> None:
        await self._get_graph()

    async def shutdown(self) -> None:
        self._graph = None
        await self._checkpointer_factory.close()

    async def start(
        self,
        *,
        workflow_run_id: str,
        application: dict[str, Any],
        fail_risk_once: bool,
        fail_credit_randomly: bool,
        crash_after_executor: str | None,
    ) -> list[dict[str, Any]]:
        graph = await self._get_graph()
        workflow_id = GRAPH_NAME
        claimed = self._repository.create_workflow_run(
            workflow_run_id,
            str(application["application_id"]),
            str(application["applicant_name"]),
            workflow_type=workflow_id,
        )
        if not claimed:
            raise WorkflowRunAlreadyClaimedError(workflow_run_id)
        self._repository.log_event(
            workflow_run_id,
            "workflow_start",
            "main",
            {"application_id": application["application_id"], "workflow_id": workflow_id},
        )
        config = {"configurable": {"thread_id": workflow_run_id}}
        try:
            with workflow_stage_span(
                "underwriting.run",
                {
                    "workflow.run_id": workflow_run_id,
                    "underwriting.application_id": application["application_id"],
                },
            ):
                result = await graph.ainvoke(
                    {
                        "workflow_run_id": workflow_run_id,
                        "application": application,
                        "fail_risk_once": fail_risk_once,
                        "fail_credit_randomly": fail_credit_randomly,
                        "crash_after_executor": crash_after_executor,
                    },
                    config=config,
                )
        except Exception as exc:
            self._repository.update_workflow_run_status(workflow_run_id, "CRASHED")
            self._repository.log_event(
                workflow_run_id,
                "workflow_crashed",
                "main",
                {"error": str(exc)},
            )
            raise
        self._repository.update_workflow_run_status(workflow_run_id, "COMPLETED")
        outputs = self._outputs_from_result(result)
        self._repository.log_event(
            workflow_run_id,
            "workflow_completed",
            "main",
            {"output_count": len(outputs)},
        )
        return outputs

    async def resume(self, workflow_run_id: str) -> list[dict[str, Any]]:
        run = self._repository.get_workflow_run(workflow_run_id)
        if run is None:
            raise ValueError(f"run not found: {workflow_run_id}")
        if run.get("status") == "COMPLETED":
            raise ValueError(f"run is already COMPLETED: {workflow_run_id}")

        checkpoint_id = self._repository.latest_checkpoint_id(workflow_run_id)
        if not checkpoint_id:
            raise ValueError(f"No checkpoints available for run {workflow_run_id}")

        self._repository.log_event(
            workflow_run_id,
            "resume_requested",
            "main",
            {
                "checkpoint_id": checkpoint_id,
                "note": "loading native LangGraph checkpoint from postgres",
            },
        )

        graph = await self._get_graph()
        config = {"configurable": {"thread_id": workflow_run_id}}
        try:
            with workflow_stage_span(
                "underwriting.resume",
                {
                    "workflow.run_id": workflow_run_id,
                    "workflow.checkpoint_id": checkpoint_id,
                },
            ):
                result = await graph.ainvoke(None, config=config)
        except Exception as exc:
            self._repository.update_workflow_run_status(workflow_run_id, "CRASHED")
            self._repository.log_event(
                workflow_run_id,
                "workflow_crashed",
                "main",
                {"error": str(exc)},
            )
            raise
        self._repository.update_workflow_run_status(workflow_run_id, "COMPLETED")
        outputs = self._outputs_from_result(result)
        self._repository.log_event(
            workflow_run_id,
            "resume_completed",
            "main",
            {"output_count": len(outputs)},
        )
        return outputs

    async def _get_graph(self) -> Any:
        if self._graph is not None:
            return self._graph
        async with self._lock:
            if self._graph is None:
                checkpointer = await self._checkpointer_factory.get()
                self._graph = build_underwriting_graph(
                    self._node_dependencies,
                    checkpointer=checkpointer,
                )
            return self._graph

    @staticmethod
    def _outputs_from_result(result: dict[str, Any]) -> list[dict[str, Any]]:
        final_decision = result.get("final_decision")
        return [final_decision] if isinstance(final_decision, dict) else []
