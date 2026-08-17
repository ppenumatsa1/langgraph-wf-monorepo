from __future__ import annotations

import asyncio
from contextlib import contextmanager

from opentelemetry import trace
from starlette.requests import Request
from starlette.responses import Response

from app.core.observability import instrument_http_request


def test_health_request_bypasses_manual_telemetry(monkeypatch) -> None:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/health",
            "raw_path": b"/health",
            "query_string": b"",
            "headers": [],
            "scheme": "http",
            "server": ("testserver", 80),
        }
    )

    def unexpected_tracer():
        raise AssertionError("health checks must not create a manual span")

    async def call_next(_request: Request) -> Response:
        return Response(status_code=204)

    monkeypatch.setattr("app.core.observability.get_tracer", unexpected_tracer)

    response = asyncio.run(instrument_http_request(request, call_next))

    assert response.status_code == 204


def test_non_health_request_uses_server_span_kind(monkeypatch) -> None:
    captured: dict[str, object] = {}
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/underwriting/ag-ui",
            "raw_path": b"/api/v1/underwriting/ag-ui",
            "query_string": b"",
            "headers": [],
            "scheme": "http",
            "server": ("testserver", 80),
        }
    )

    class FakeSpan:
        def set_attribute(self, key: str, value: object) -> None:
            captured[key] = value

    class FakeTracer:
        @contextmanager
        def start_as_current_span(self, name: str, *, kind: trace.SpanKind):
            captured["name"] = name
            captured["kind"] = kind
            yield FakeSpan()

    async def call_next(_request: Request) -> Response:
        return Response(status_code=202)

    monkeypatch.setattr("app.core.observability.get_tracer", lambda: FakeTracer())

    response = asyncio.run(instrument_http_request(request, call_next))

    assert response.status_code == 202
    assert captured["name"] == "HTTP POST /api/v1/underwriting/ag-ui"
    assert captured["kind"] is trace.SpanKind.SERVER


def test_polling_read_request_bypasses_manual_telemetry(monkeypatch) -> None:
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/v1/underwriting/runs",
            "raw_path": b"/api/v1/underwriting/runs",
            "query_string": b"",
            "headers": [],
            "scheme": "http",
            "server": ("testserver", 80),
        }
    )

    async def call_next(_request: Request) -> Response:
        return Response(status_code=200)

    monkeypatch.setattr(
        "app.core.observability.get_tracer",
        lambda: (_ for _ in ()).throw(AssertionError("polling GET must not create a manual span")),
    )

    response = asyncio.run(instrument_http_request(request, call_next))

    assert response.status_code == 200
