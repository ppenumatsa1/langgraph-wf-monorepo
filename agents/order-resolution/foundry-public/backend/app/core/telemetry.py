from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags

_OBSERVABILITY_CONFIGURED = False
logger = logging.getLogger(__name__)
_SENSITIVE_ATTRIBUTE_KEYS = {
    "comments",
    "data",
    "details",
    "input",
    "message",
    "mcp_result",
    "output",
    "payload",
    "prompt",
    "question",
    "request",
    "response",
    "result",
    "summary",
    "user_message",
}


@dataclass(frozen=True)
class ObservabilityStatus:
    telemetry_enabled: bool
    instrumentation_enabled: bool
    sensitive_content_enabled: bool
    azure_monitor_configured: bool
    otlp_configured: bool


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _record_content_enabled() -> bool:
    return _env_bool("OTEL_RECORD_CONTENT", False)


def _safe_attributes(attributes: dict[str, Any] | None) -> dict[str, Any]:
    if not attributes:
        return {}
    record_content = _record_content_enabled()
    safe: dict[str, Any] = {}
    for key, value in attributes.items():
        normalized = key.lower().replace("-", "_")
        if value is None:
            continue
        if not record_content and normalized in _SENSITIVE_ATTRIBUTE_KEYS:
            continue
        if isinstance(value, str | bool | int | float):
            safe[key] = value
    return safe


def _configure_azure_monitor(connection_string: str, resource: Any) -> bool:
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor
    except ImportError:
        return False

    try:
        configure_azure_monitor(connection_string=connection_string, resource=resource)
    except TypeError:
        try:
            configure_azure_monitor(connection_string=connection_string)
        except Exception:
            logger.exception("Azure Monitor telemetry configuration failed")
            return False
    except Exception:
        logger.exception("Azure Monitor telemetry configuration failed")
        return False
    return True


def _create_observability_resource(service_name: str) -> Any:
    try:
        return Resource.create(
            {
                "service.name": service_name,
                "service.version": "0.2.0",
                "deployment.environment": os.getenv("APP_ENV", "local"),
            }
        )
    except Exception:
        logger.exception("Telemetry resource creation failed")
        return None


def setup_observability() -> ObservabilityStatus:
    global _OBSERVABILITY_CONFIGURED

    telemetry_enabled = _env_bool("ENABLE_TELEMETRY", True)
    instrumentation_enabled = telemetry_enabled and _env_bool("ENABLE_INSTRUMENTATION", True)
    sensitive_content_enabled = _record_content_enabled()
    if not telemetry_enabled:
        return ObservabilityStatus(
            telemetry_enabled=False,
            instrumentation_enabled=False,
            sensitive_content_enabled=sensitive_content_enabled,
            azure_monitor_configured=False,
            otlp_configured=False,
        )

    service_name = os.getenv("OTEL_SERVICE_NAME", "langgraph-order-resolution")
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
    canonical_connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip()
    alias_connection_string = os.getenv("APPINSIGHTS_CONNECTION_STRING", "").strip()
    # Prefer alias when it carries the full region-aware connection string while
    # the canonical variable is intentionally compacted for hosted runtime bootstrap.
    if "IngestionEndpoint=" in alias_connection_string:
        app_insights_connection_string = alias_connection_string
    else:
        app_insights_connection_string = canonical_connection_string or alias_connection_string
    if not app_insights_connection_string:
        instrumentation_key = os.getenv("APPINSIGHTS_INSTRUMENTATIONKEY") or os.getenv(
            "APPINSIGHTS_INSTRUMENTATION_KEY"
        )
        if instrumentation_key:
            app_insights_connection_string = f"InstrumentationKey={instrumentation_key}"
    if app_insights_connection_string:
        app_insights_connection_string = app_insights_connection_string.strip().rstrip(";")

    resource = _create_observability_resource(service_name)

    azure_monitor_configured = False
    if app_insights_connection_string and not _OBSERVABILITY_CONFIGURED:
        azure_monitor_configured = _configure_azure_monitor(
            app_insights_connection_string, resource
        )

    if not azure_monitor_configured and not _OBSERVABILITY_CONFIGURED:
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)
    else:
        provider = trace.get_tracer_provider()

    otlp_configured = False
    if otlp_endpoint and hasattr(provider, "add_span_processor") and not _OBSERVABILITY_CONFIGURED:
        try:
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            otlp_configured = True
        except Exception:
            logger.exception("OTLP telemetry configuration failed")

    _OBSERVABILITY_CONFIGURED = True
    return ObservabilityStatus(
        telemetry_enabled=True,
        instrumentation_enabled=instrumentation_enabled,
        sensitive_content_enabled=sensitive_content_enabled,
        azure_monitor_configured=azure_monitor_configured,
        otlp_configured=otlp_configured,
    )


def enable_langgraph_auto_tracing() -> bool:
    if not _env_bool("ENABLE_TELEMETRY", True):
        return False
    if not _env_bool("ENABLE_INSTRUMENTATION", True):
        return False
    if not _env_bool("ENABLE_LANGGRAPH_AUTO_TRACING", True):
        return False
    try:
        from langchain_azure_ai.callbacks.tracers import enable_auto_tracing
    except ImportError:
        logger.warning("Azure AI LangGraph auto-tracing package is unavailable")
        return False

    try:
        enable_auto_tracing(
            enable_content_recording=False,
            trace_all_langgraph_nodes=True,
            auto_configure_azure_monitor=False,
            trace_state=False,
        )
    except Exception:
        logger.exception("Azure AI LangGraph auto-tracing setup failed")
        return False
    return True


def instrument_fastapi_app(app: Any) -> bool:
    if not _env_bool("ENABLE_TELEMETRY", True):
        return False
    if not _env_bool("ENABLE_INSTRUMENTATION", True):
        return False
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    except ImportError:
        logger.warning("FastAPI OpenTelemetry instrumentation package is unavailable")
        return False

    try:
        FastAPIInstrumentor.instrument_app(
            app,
            excluded_urls=r".*/(?:api/)?health(?:\?.*)?$|.*/api/chat/stream/.*",
        )
    except Exception:
        logger.exception("FastAPI telemetry instrumentation setup failed")
        return False
    return True


def get_tracer(name: str):
    return trace.get_tracer(name)


def _parent_context_from_trace(trace_context: dict[str, str] | None):
    if not trace_context:
        return None
    trace_id = trace_context.get("trace_id")
    span_id = trace_context.get("span_id")
    if not trace_id or not span_id:
        return None
    try:
        span_context = SpanContext(
            trace_id=int(trace_id, 16),
            span_id=int(span_id, 16),
            is_remote=True,
            trace_flags=TraceFlags(TraceFlags.SAMPLED),
        )
    except ValueError:
        logger.warning("Invalid persisted trace context ignored")
        return None
    if not span_context.is_valid:
        return None
    return trace.set_span_in_context(NonRecordingSpan(span_context))


@contextmanager
def workflow_stage_span(
    stage: str,
    attributes: dict[str, Any] | None = None,
    *,
    parent_trace_context: dict[str, str] | None = None,
):
    tracer = get_tracer("app.workflow")
    parent_context = _parent_context_from_trace(parent_trace_context)
    with tracer.start_as_current_span(
        f"workflow.{stage}",
        attributes=_safe_attributes(attributes),
        context=parent_context,
    ) as span:
        yield span


def current_trace_context() -> dict[str, str] | None:
    span_context = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return None
    return {
        "trace_id": f"{span_context.trace_id:032x}",
        "span_id": f"{span_context.span_id:016x}",
    }


def record_business_event(name: str, attributes: dict[str, Any] | None = None) -> None:
    span = trace.get_current_span()
    if span and span.is_recording():
        span.add_event(name, attributes=_safe_attributes(attributes))


def record_workflow_event(event: Any) -> None:
    attributes = {
        "event.type": getattr(event, "type", None),
        "workflow.thread_id": getattr(event, "thread_id", None),
    }
    payload = getattr(event, "payload", None)
    if isinstance(payload, dict):
        attributes.update(
            {
                "workflow.agent": payload.get("agent"),
                "workflow.status": payload.get("status"),
                "workflow.action": payload.get("action"),
            }
        )
        if _record_content_enabled():
            attributes["payload"] = str(payload)
    record_business_event("workflow.event", attributes)


def _reset_observability_for_tests() -> None:
    global _OBSERVABILITY_CONFIGURED
    _OBSERVABILITY_CONFIGURED = False
