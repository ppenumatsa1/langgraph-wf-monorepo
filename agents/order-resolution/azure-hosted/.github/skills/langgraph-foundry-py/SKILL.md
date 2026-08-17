---
name: langgraph-foundry-py
description: Maintain the direct LangGraph FastAPI runtime with Foundry model inference, PostgreSQL checkpoints, HITL, durable projections, and Application Insights.
---

# LangGraph + Foundry Models

- `backend/app/langgraph` owns the only workflow.
- `backend/app/main.py` is the Azure-hosted FastAPI entrypoint.
- Foundry is a model/evaluator provider only; never add a hosted application
  entrypoint, agent service, version, or invocation adapter.
- Preserve native PostgreSQL checkpoints, one pending interrupt per thread,
  replay-safe event projection, reconciliation before resume, and idempotent
  side effects.
- Preserve the six native SSE event types and redacted AG-UI/CopilotKit
  projections.
- Use `DefaultAzureCredential` and the backend managed identity for model calls.
- Production DDL remains administrator-owned.

Validation: `make test`, `make eval-backend`, `make test-e2e`.
