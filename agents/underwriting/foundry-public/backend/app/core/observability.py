from __future__ import annotations

import logging
import os
import time
import uuid
from contextvars import ContextVar
from typing import Any

from azure.monitor.opentelemetry import configure_azure_monitor
from fastapi import Request
from opentelemetry import trace
from opentelemetry.instrumentation.openai_v2 import OpenAIInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
_openai_instrumented = False


class RequestContextFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("-")
        return True


def configure_observability(log_level: str, service_name: str = "underwriting-public-api") -> None:
    global _openai_instrumented

    root = logging.getLogger()
    if not root.handlers:
        logging.basicConfig(
            level=getattr(logging, log_level.upper(), logging.INFO),
            format="%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s",
        )
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    has_filter = any(isinstance(f, RequestContextFilter) for f in root.filters)
    if not has_filter:
        root.addFilter(RequestContextFilter())
        for handler in root.handlers:
            handler.addFilter(RequestContextFilter())

    resource = Resource(attributes={SERVICE_NAME: os.getenv("OTEL_SERVICE_NAME", service_name)})
    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip().rstrip(";")
    if connection_string:
        configure_azure_monitor(connection_string=connection_string, resource=resource)
        if not _openai_instrumented:
            OpenAIInstrumentor().instrument()
            _openai_instrumented = True
        return

    provider = trace.get_tracer_provider()
    if not isinstance(provider, TracerProvider):
        provider = TracerProvider(resource=resource)
        if os.getenv("ENABLE_CONSOLE_TRACING", "").lower() in {"1", "true", "yes", "on"}:
            provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
        trace.set_tracer_provider(provider)


def get_tracer() -> trace.Tracer:
    return trace.get_tracer("underwriting-langgraph-backend")


def _should_trace_http_request(request: Request) -> bool:
    return request.method not in {"GET", "HEAD", "OPTIONS"} and request.url.path != "/health"


def log_with_context(logger: logging.Logger, message: str, **fields: Any) -> None:
    context = " ".join(f"{k}={v}" for k, v in fields.items())
    logger.info("%s %s", message, context)


async def instrument_http_request(request: Request, call_next):
    if not _should_trace_http_request(request):
        return await call_next(request)

    logger = logging.getLogger("app.http")
    tracer = get_tracer()
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    token = request_id_var.set(request_id)
    start = time.perf_counter()
    try:
        with tracer.start_as_current_span(
            f"HTTP {request.method} {request.url.path}",
            kind=trace.SpanKind.SERVER,
        ) as span:
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.target", request.url.path)
            span.set_attribute("http.request_id", request_id)
            try:
                response = await call_next(request)
            except Exception as exc:
                duration_ms = round((time.perf_counter() - start) * 1000, 2)
                logger.exception(
                    "http_request_failed method=%s path=%s duration_ms=%s error=%s",
                    request.method,
                    request.url.path,
                    duration_ms,
                    str(exc),
                )
                raise
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            response.headers["x-request-id"] = request_id
            span.set_attribute("http.status_code", response.status_code)
            span.set_attribute("http.duration_ms", duration_ms)
            logger.info(
                "http_request method=%s path=%s status=%s duration_ms=%s",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
            return response
    finally:
        request_id_var.reset(token)
