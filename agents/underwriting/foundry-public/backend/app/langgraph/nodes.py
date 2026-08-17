from __future__ import annotations

import asyncio
import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings
from app.core.telemetry import workflow_attributes, workflow_stage_span
from app.infrastructure.persistence.idempotency_store import IdempotencyStore
from app.infrastructure.persistence.workflow_run_repository import WorkflowRunRepository
from app.modules.underwriting import events as event_types
from app.modules.underwriting.decisions import build_final_rationale, compute_decision


@dataclass(frozen=True)
class NodeDependencies:
    repository: WorkflowRunRepository
    idempotency_store: IdempotencyStore
    settings: Settings
    llm_client: Any | None


class UnderwritingNodes:
    def __init__(self, dependencies: NodeDependencies) -> None:
        self._dependencies = dependencies

    async def init_context(self, state: dict[str, Any]) -> dict[str, Any]:
        workflow_run_id = str(state["workflow_run_id"])
        application = dict(state["application"])
        application_id = str(application["application_id"])
        expected_checks = ["risk", "credit", "medical", "driving"]
        with workflow_stage_span(
            "stage.init_context",
            {
                "workflow.run_id": workflow_run_id,
                "underwriting.application_id": application_id,
                "workflow.executor": "init_context",
            },
        ):
            self._dependencies.repository.write_business_state(
                workflow_run_id,
                application_id,
                "underwriting_context",
                {
                    "application_id": application_id,
                    "applicant_name": application["applicant_name"],
                    "age": application["age"],
                    "income": application["income"],
                    "requested_coverage": application["requested_coverage"],
                    "expected_checks": expected_checks,
                    "completed_checks": [],
                    "child_results": {},
                    "final_decision": None,
                    "final_decision_emitted": False,
                },
            )
            self._dependencies.repository.write_business_state(
                workflow_run_id,
                application_id,
                "aggregation_state",
                {
                    "expected_checks": expected_checks,
                    "completed_checks": [],
                    "child_results": {},
                },
            )
            self._dependencies.repository.log_event(
                workflow_run_id,
                event_types.INIT_CONTEXT,
                "init_context",
                {"application_id": application_id, "message_received": True},
            )
        return {
            "workflow_run_id": workflow_run_id,
            "application": application,
            "application_id": application_id,
            "applicant_name": str(application["applicant_name"]),
            "fail_risk_once": bool(
                state.get("fail_risk_once", self._dependencies.settings.fail_risk_once)
            ),
            "fail_credit_randomly": bool(
                state.get(
                    "fail_credit_randomly",
                    self._dependencies.settings.fail_credit_randomly,
                )
            ),
            "crash_after_executor": state.get(
                "crash_after_executor",
                self._dependencies.settings.crash_after_executor or None,
            ),
            "expected_checks": expected_checks,
        }

    async def risk_score(self, state: dict[str, Any]) -> dict[str, Any]:
        application = dict(state["application"])
        return await self._run_check(
            state,
            check_type="risk",
            executor_name="risk_score",
            operation_name="risk_check",
            operation=lambda: {
                "score": round(
                    max(
                        0.0,
                        min(
                            1.0,
                            (float(application["age"]) / 100.0)
                            + (float(application["requested_coverage"]) / 1_000_000.0),
                        ),
                    ),
                    3,
                ),
                "details": {"model": "deterministic-risk-v1"},
            },
        )

    async def credit_check(self, state: dict[str, Any]) -> dict[str, Any]:
        application = dict(state["application"])
        return await self._run_check(
            state,
            check_type="credit",
            executor_name="credit_check",
            operation_name="credit_check",
            operation=lambda: {
                "score": round(
                    min(1.0, max(0.0, int(application["credit_score"]) / 850.0)),
                    3,
                ),
                "details": {"bureau": "demo-credit-bureau"},
            },
        )

    async def medical_check(self, state: dict[str, Any]) -> dict[str, Any]:
        application = dict(state["application"])
        disclosures = str(application["health_disclosures"])
        return await self._run_check(
            state,
            check_type="medical",
            executor_name="medical_check",
            operation_name="medical_check",
            operation=lambda: {
                "score": 0.4 if "chronic" in disclosures.lower() else 0.85,
                "details": {"disclosures": disclosures},
            },
        )

    async def driving_check(self, state: dict[str, Any]) -> dict[str, Any]:
        application = dict(state["application"])
        history = str(application["driving_history"])
        return await self._run_check(
            state,
            check_type="driving",
            executor_name="driving_check",
            operation_name="driving_check",
            operation=lambda: {
                "score": 0.35
                if any(flag in history.lower() for flag in ("dui", "accident"))
                else 0.9,
                "details": {"history": history},
            },
        )

    async def fan_in_aggregator(self, state: dict[str, Any]) -> dict[str, Any]:
        workflow_run_id = str(state["workflow_run_id"])
        application_id = str(state["application_id"])
        expected_checks = [str(item) for item in state.get("expected_checks", [])]
        child_results = self._dedupe_results(state.get("check_results", []))
        with workflow_stage_span(
            "stage.fan_in",
            {
                "workflow.run_id": workflow_run_id,
                "underwriting.application_id": application_id,
                "workflow.executor": "fan_in_aggregator",
            },
        ):
            self._dependencies.repository.write_business_state(
                workflow_run_id,
                application_id,
                "aggregation_state",
                {
                    "expected_checks": expected_checks,
                    "completed_checks": list(child_results.keys()),
                    "child_results": child_results,
                },
            )
        return {}

    async def final_decision(self, state: dict[str, Any]) -> dict[str, Any]:
        workflow_run_id = str(state["workflow_run_id"])
        application_id = str(state["application_id"])
        child_results = self._dedupe_results(state.get("check_results", []))
        score_breakdown = {
            key: float(value["score"])
            for key, value in child_results.items()
            if isinstance(value, dict) and "score" in value
        }
        avg_score = sum(score_breakdown.values()) / max(1, len(score_breakdown))
        decision = compute_decision(avg_score, score_breakdown)
        with workflow_stage_span(
            "stage.final_decision",
            {
                **workflow_attributes(
                    type(
                        "DecisionContext",
                        (),
                        {"workflow_run_id": workflow_run_id, "application_id": application_id},
                    )(),
                    "final_decision",
                ),
            },
        ):
            idempotency_key = self._dependencies.idempotency_store.compose_key(
                workflow_run_id,
                "final_decision",
                application_id,
            )
            payload = self._dependencies.repository.get_underwriting_result_by_key(idempotency_key)
            replayed = payload is not None
            if payload is None:
                rationale = await build_final_rationale(
                    decision=decision,
                    average_score=avg_score,
                    score_breakdown=score_breakdown,
                    llm_client=self._dependencies.llm_client,
                )
                payload = {
                    "workflow_run_id": workflow_run_id,
                    "application_id": application_id,
                    "decision": decision.value,
                    "rationale": rationale,
                    "score_breakdown": score_breakdown,
                    "idempotency_key": idempotency_key,
                }
                self._dependencies.repository.save_underwriting_result(
                    workflow_run_id,
                    application_id,
                    "final_decision",
                    payload,
                    idempotency_key,
                )
                self._dependencies.repository.upsert_idempotency(
                    idempotency_key,
                    "final_decision",
                    "completed",
                    payload,
                )
            self._dependencies.repository.write_business_state(
                workflow_run_id,
                application_id,
                "final_decision",
                payload,
            )
            self._dependencies.repository.update_latest_output(
                workflow_run_id,
                payload,
            )
            if replayed:
                with workflow_stage_span(
                    "stage.idempotency_skip",
                    {
                        "workflow.run_id": workflow_run_id,
                        "underwriting.application_id": application_id,
                        "workflow.executor": "final_decision",
                    },
                ):
                    self._dependencies.repository.log_event(
                        workflow_run_id,
                        event_types.IDEMPOTENCY_SKIP,
                        "final_decision",
                        {"idempotency_key": payload["idempotency_key"]},
                    )
            else:
                self._dependencies.repository.log_event(
                    workflow_run_id,
                    event_types.FINAL_DECISION,
                    "final_decision",
                    payload,
                )
            self._maybe_crash_after_executor(state, workflow_run_id, "final_decision")
        return {"final_decision": payload}

    async def _run_check(
        self,
        state: dict[str, Any],
        *,
        check_type: str,
        executor_name: str,
        operation_name: str,
        operation: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        workflow_run_id = str(state["workflow_run_id"])
        application = dict(state["application"])
        application_id = str(application["application_id"])
        idempotency_key = self._dependencies.idempotency_store.compose_key(
            workflow_run_id,
            operation_name,
            application_id,
        )
        with workflow_stage_span(
            f"stage.{operation_name}",
            {
                "workflow.run_id": workflow_run_id,
                "underwriting.application_id": application_id,
                "underwriting.check_type": check_type,
                "workflow.executor": executor_name,
            },
        ):
            persisted_result = self._dependencies.repository.get_underwriting_result_by_key(
                idempotency_key
            )
            if persisted_result is not None:
                self._dependencies.repository.upsert_idempotency(
                    idempotency_key,
                    operation_name,
                    "completed",
                    persisted_result,
                )
                with workflow_stage_span(
                    "stage.idempotency_skip",
                    {
                        "workflow.run_id": workflow_run_id,
                        "underwriting.application_id": application_id,
                        "underwriting.check_type": check_type,
                        "workflow.executor": executor_name,
                    },
                ):
                    self._dependencies.repository.log_event(
                        workflow_run_id,
                        event_types.IDEMPOTENCY_SKIP,
                        executor_name,
                        {"idempotency_key": idempotency_key, "source": "result_row"},
                    )
                self._dependencies.repository.record_fan_in_progress(
                    workflow_run_id,
                    application_id,
                    [str(item) for item in state.get("expected_checks", [])],
                    persisted_result,
                )
                self._maybe_crash_after_executor(state, workflow_run_id, executor_name)
                return {"check_results": [persisted_result]}

            payload = await self._retry_check(
                state=state,
                workflow_run_id=workflow_run_id,
                application_id=application_id,
                check_type=check_type,
                executor_name=executor_name,
                operation_name=operation_name,
                idempotency_key=idempotency_key,
                operation=operation,
            )
            self._dependencies.repository.save_underwriting_result(
                workflow_run_id,
                application_id,
                check_type,
                payload,
                idempotency_key,
            )
            self._dependencies.repository.log_event(
                workflow_run_id,
                event_types.CHECK_COMPLETED,
                executor_name,
                payload,
            )
            self._dependencies.repository.record_fan_in_progress(
                workflow_run_id,
                application_id,
                [str(item) for item in state.get("expected_checks", [])],
                payload,
            )
            self._maybe_crash_after_executor(state, workflow_run_id, executor_name)
            return {"check_results": [payload]}

    async def _retry_check(
        self,
        *,
        state: dict[str, Any],
        workflow_run_id: str,
        application_id: str,
        check_type: str,
        executor_name: str,
        operation_name: str,
        idempotency_key: str,
        operation: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        attempts = max(1, int(self._dependencies.settings.retry_max_attempts))
        for attempt in range(1, attempts + 1):
            with workflow_stage_span(
                "stage.retry_attempt",
                {
                    "workflow.run_id": workflow_run_id,
                    "underwriting.application_id": application_id,
                    "underwriting.check_type": check_type,
                    "workflow.executor": executor_name,
                    "workflow.retry_attempt": attempt,
                },
            ):
                self._dependencies.repository.log_event(
                    workflow_run_id,
                    event_types.RETRY_ATTEMPT,
                    executor_name,
                    {"operation_name": operation_name, "attempt": attempt},
                )
            try:
                self._maybe_inject_failure(
                    state=state,
                    workflow_run_id=workflow_run_id,
                    check_type=check_type,
                    executor_name=executor_name,
                    application_id=application_id,
                    idempotency_key=idempotency_key,
                )
                result = operation()
                return {
                    "workflow_run_id": workflow_run_id,
                    "application_id": application_id,
                    "check_type": check_type,
                    "score": float(result["score"]),
                    "details": result["details"],
                    "idempotency_key": idempotency_key,
                }
            except Exception as exc:
                if attempt >= attempts:
                    with workflow_stage_span(
                        "stage.retry_exhausted",
                        {
                            "workflow.run_id": workflow_run_id,
                            "underwriting.application_id": application_id,
                            "underwriting.check_type": check_type,
                            "workflow.executor": executor_name,
                            "workflow.retry_attempt": attempt,
                        },
                    ):
                        self._dependencies.repository.log_event(
                            workflow_run_id,
                            event_types.RETRY_EXHAUSTED,
                            executor_name,
                            {
                                "operation_name": operation_name,
                                "attempt": attempt,
                                "error": str(exc),
                            },
                        )
                    raise
                delay_seconds = (
                    (2 ** (attempt - 1)) * self._dependencies.settings.retry_base_delay_ms
                    + random.randint(0, self._dependencies.settings.retry_jitter_ms)
                ) / 1000.0
                with workflow_stage_span(
                    "stage.retry_backoff",
                    {
                        "workflow.run_id": workflow_run_id,
                        "underwriting.application_id": application_id,
                        "underwriting.check_type": check_type,
                        "workflow.executor": executor_name,
                        "workflow.retry_attempt": attempt,
                        "workflow.retry_delay_ms": round(delay_seconds * 1000),
                    },
                ):
                    self._dependencies.repository.log_event(
                        workflow_run_id,
                        event_types.RETRY_BACKOFF,
                        executor_name,
                        {
                            "operation_name": operation_name,
                            "attempt": attempt,
                            "error": str(exc),
                            "delay_seconds": delay_seconds,
                        },
                    )
                await asyncio.sleep(delay_seconds)
        raise RuntimeError(f"{operation_name} exhausted unexpectedly")

    def _maybe_inject_failure(
        self,
        *,
        state: dict[str, Any],
        workflow_run_id: str,
        application_id: str,
        check_type: str,
        executor_name: str,
        idempotency_key: str,
    ) -> None:
        fail_risk_once = bool(
            state.get("fail_risk_once", self._dependencies.settings.fail_risk_once)
        )
        fail_credit_randomly = bool(
            state.get(
                "fail_credit_randomly",
                self._dependencies.settings.fail_credit_randomly,
            )
        )
        if check_type == "risk" and fail_risk_once:
            marker_key = f"{idempotency_key}:fail-once"
            marker = self._dependencies.repository.get_idempotency(marker_key)
            if marker is None:
                with workflow_stage_span(
                    "stage.failure_injected",
                    {
                        "workflow.run_id": workflow_run_id,
                        "underwriting.application_id": application_id,
                        "underwriting.check_type": check_type,
                        "workflow.executor": executor_name,
                        "workflow.failure_mode": "risk_once",
                    },
                ):
                    self._dependencies.repository.upsert_idempotency(
                        marker_key,
                        "failure-injection",
                        "completed",
                        {"injected": True},
                    )
                raise RuntimeError("Injected FAIL_RISK_ONCE failure")

        if check_type == "credit" and fail_credit_randomly:
            if self._dependencies.repository.should_fail_credit_randomly():
                with workflow_stage_span(
                    "stage.failure_injected",
                    {
                        "workflow.run_id": workflow_run_id,
                        "underwriting.application_id": application_id,
                        "underwriting.check_type": check_type,
                        "workflow.executor": executor_name,
                        "workflow.failure_mode": "credit_random",
                    },
                ):
                    pass
                raise RuntimeError("Injected FAIL_CREDIT_RANDOMLY failure")

    def _maybe_crash_after_executor(
        self,
        state: dict[str, Any],
        workflow_run_id: str,
        executor_name: str,
    ) -> None:
        target = str(
            state.get(
                "crash_after_executor",
                self._dependencies.settings.crash_after_executor,
            )
            or ""
        ).strip()
        if not target or target != executor_name:
            return
        marker_key = f"crash:{workflow_run_id}:{executor_name}"
        marker = self._dependencies.repository.get_idempotency(marker_key)
        if marker is None:
            self._dependencies.repository.upsert_idempotency(
                marker_key,
                "crash-injection",
                "completed",
                {"executor_name": executor_name},
            )
            raise RuntimeError(f"Injected crash after executor {executor_name}")

    @staticmethod
    def _dedupe_results(values: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
        deduped: dict[str, dict[str, Any]] = {}
        for value in values:
            if not isinstance(value, dict):
                continue
            check_type = value.get("check_type")
            if isinstance(check_type, str):
                deduped[check_type] = value
        return deduped
