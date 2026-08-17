from __future__ import annotations

import logging

from app.core.config import Settings
from app.infrastructure.foundry.responses_client import UnderwritingResponsesClient
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository
from app.modules.underwriting.copilot import (
    SafeRunExplanationRequest,
    build_safe_explanation,
)
from app.modules.underwriting.ports import (
    UnderwritingHostedWorkflowPort,
    UnderwritingRunRepositoryPort,
)
from app.modules.underwriting.projections import build_safe_selected_run_context

logger = logging.getLogger(__name__)


class UnderwritingCopilotBridge:
    """Allowlisted bridge that projects a selected run without reading private payloads."""

    def __init__(
        self,
        settings: Settings,
        *,
        responses_client: UnderwritingHostedWorkflowPort | None = None,
        repository: UnderwritingRunRepositoryPort | None = None,
    ):
        self.settings = settings
        self.repository = repository or WorkflowRunRepository()
        self._responses_client = responses_client or UnderwritingResponsesClient(settings)

    async def explain(self, workflow_run_id: str | None, intent: str) -> str:
        if workflow_run_id is None:
            return "Select an underwriting run to view its safe execution summary."
        context = self._safe_context(workflow_run_id)
        if context is None:
            return "The selected run is unavailable."
        expected_explanation = build_safe_explanation(context, intent)
        if self.settings.execution_mode == "local":
            return expected_explanation
        response = await self._responses_client.invoke(
            SafeRunExplanationRequest(
                workflow_run_id=workflow_run_id,
                intent=intent,
                context=context,
            )
        )
        if (
            response.get("workflow_run_id") == workflow_run_id
            and response.get("explanation") == expected_explanation
        ):
            return expected_explanation
        logger.warning(
            "Hosted assistant response did not match the safe deterministic projection for run %s",
            workflow_run_id,
        )
        return expected_explanation

    def _safe_context(self, workflow_run_id: str):
        return build_safe_selected_run_context(self.repository, workflow_run_id)
