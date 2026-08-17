from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

from app.modules.underwriting.models import UnderwritingApplication

HOSTED_WORKFLOW_PROTOCOL = "underwriting-hosted-workflow/v1"
HostedWorkflowAction = Literal["start", "resume"]


@dataclass(frozen=True, slots=True)
class HostedWorkflowEnvelope:
    workflow_run_id: str
    action: HostedWorkflowAction
    application: UnderwritingApplication | None = None
    fail_risk_once: bool = False
    fail_credit_randomly: bool = False
    crash_after_executor: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "protocol": HOSTED_WORKFLOW_PROTOCOL,
            "workflow_run_id": self.workflow_run_id,
            "action": self.action,
        }
        if self.application is not None:
            payload["application"] = self.application.to_dict()
        if self.action == "start":
            payload["options"] = {
                "fail_risk_once": self.fail_risk_once,
                "fail_credit_randomly": self.fail_credit_randomly,
                "crash_after_executor": self.crash_after_executor,
            }
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> HostedWorkflowEnvelope:
        if payload.get("protocol") != HOSTED_WORKFLOW_PROTOCOL:
            raise ValueError("Unsupported hosted underwriting workflow protocol")

        workflow_run_id = payload.get("workflow_run_id")
        if not isinstance(workflow_run_id, str) or not re.fullmatch(
            r"run-[A-Za-z0-9_-]{1,60}", workflow_run_id
        ):
            raise ValueError("workflow_run_id must be a non-empty value beginning with 'run-'")

        action = payload.get("action")
        if action not in {"start", "resume"}:
            raise ValueError("action must be either 'start' or 'resume'")

        if action == "resume":
            return cls(workflow_run_id=workflow_run_id, action="resume")

        application_payload = payload.get("application")
        if not isinstance(application_payload, dict):
            raise ValueError("start requires an application object")
        try:
            application = UnderwritingApplication(**application_payload)
        except (TypeError, ValueError) as exc:
            raise ValueError("start application is invalid") from exc
        _validate_application(application)

        options = payload.get("options", {})
        if not isinstance(options, dict):
            raise ValueError("options must be an object")
        fail_risk_once = _bool_option(options, "fail_risk_once")
        fail_credit_randomly = _bool_option(options, "fail_credit_randomly")
        crash_after_executor = options.get("crash_after_executor")
        if crash_after_executor is not None and not isinstance(crash_after_executor, str):
            raise ValueError("crash_after_executor must be a string or null")

        return cls(
            workflow_run_id=workflow_run_id,
            action="start",
            application=application,
            fail_risk_once=fail_risk_once,
            fail_credit_randomly=fail_credit_randomly,
            crash_after_executor=crash_after_executor,
        )


def _bool_option(options: dict[str, Any], name: str) -> bool:
    value = options.get(name, False)
    if not isinstance(value, bool):
        raise ValueError(f"{name} must be a boolean")
    return value


def _validate_application(application: UnderwritingApplication) -> None:
    if not all(
        isinstance(value, str)
        for value in (
            application.application_id,
            application.applicant_name,
            application.health_disclosures,
            application.driving_history,
        )
    ):
        raise ValueError("start application text fields must be strings")
    if isinstance(application.age, bool) or not isinstance(application.age, int):
        raise ValueError("start application age must be an integer")
    if isinstance(application.credit_score, bool) or not isinstance(application.credit_score, int):
        raise ValueError("start application credit_score must be an integer")
    for value in (application.income, application.requested_coverage):
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError("start application financial fields must be numeric")
