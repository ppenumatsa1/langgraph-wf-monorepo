from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace
from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import Status, StatusCode

logger = logging.getLogger(__name__)
_configured = False
_workflow_context: ContextVar[dict[str, str] | None] = ContextVar("workflow_context", default=None)


def _connection_string() -> str:
    return (
        (
            os.getenv("UNDERWRITING_APPINSIGHTS_CONNECTION_STRING")
            or os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
            or os.getenv("APPINSIGHTS_CONNECTION_STRING")
            or ""
        )
        .strip()
        .rstrip(";")
    )


def setup_hosted_observability() -> None:
    global _configured
    if _configured:
        return

    os.environ["OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT"] = "false"
    resource = Resource.create(
        {
            "service.name": os.getenv("OTEL_SERVICE_NAME", "underwriting-hosted"),
            "service.version": "0.3.0",
            "deployment.environment": os.getenv("APP_ENV", "production"),
        }
    )
    connection_string = _connection_string()
    if connection_string:
        configure_azure_monitor(
            connection_string=connection_string,
            resource=resource,
            sampling_ratio=1.0,
        )
    else:
        os.environ.setdefault("OTEL_METRICS_EXPORTER", "none")
        trace.set_tracer_provider(TracerProvider(resource=resource))
        logger.warning(
            "Hosted telemetry has no Application Insights connection string; spans will not be exported."
        )

    OpenAIInstrumentor().instrument()
    _configured = True


def workflow_attributes(message: Any, executor: str | None = None) -> dict[str, str]:
    application = getattr(message, "application", None)
    check_type = getattr(message, "check_type", None)
    attributes = {
        "workflow.run_id": getattr(message, "workflow_run_id", None),
        "underwriting.application_id": getattr(
            message, "application_id", getattr(application, "application_id", None)
        ),
        "underwriting.check_type": getattr(check_type, "value", check_type),
        "workflow.executor": executor,
    }
    return {key: str(value) for key, value in attributes.items() if value is not None}


@contextmanager
def workflow_telemetry_context(attributes: dict[str, str]) -> Any:
    token = _workflow_context.set({**(_workflow_context.get() or {}), **attributes})
    try:
        yield
    finally:
        _workflow_context.reset(token)


def annotate_current_span(workflow_run_id: str, action: str) -> None:
    span = trace.get_current_span()
    if span.is_recording():
        span.set_attribute("workflow.run_id", workflow_run_id)
        span.set_attribute("workflow.action", action)


@contextmanager
def workflow_stage_span(stage: str, attributes: dict[str, Any] | None = None):
    tracer = trace.get_tracer("underwriting.workflow")
    merged_attributes = {
        key: value
        for key, value in {**(_workflow_context.get() or {}), **(attributes or {})}.items()
        if value is not None
    }
    with tracer.start_as_current_span(f"workflow.{stage}", attributes=merged_attributes) as span:
        try:
            yield span
        except BaseException as exc:
            span.set_attribute("workflow.status", "failed")
            span.record_exception(exc)
            span.set_status(Status(StatusCode.ERROR, str(exc)))
            raise
        else:
            span.set_attribute("workflow.status", "completed")
            span.set_status(Status(StatusCode.OK))
