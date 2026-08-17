---
name: ag-ui-streaming-fastapi-py
description: Implement and review FastAPI AG-UI streaming endpoints that project durable underwriting workflow progress without widening the public contract.
---

# AG-UI Streaming for FastAPI (Underwriting)

Use this skill when changing streaming APIs, event envelopes, or backend-to-frontend event projection.

## Scope

- Endpoint surface: `POST /api/v1/underwriting/ag-ui`
- Route ownership: `backend/app/api/v1/routes/underwriting.py`
- Stream router: `backend/app/api/v1/routers/agui.py`
- Durable projections: `backend/app/modules/underwriting/projections.py`
- Durable read models: run, state, events, and checkpoints endpoints remain the source of truth

## Guardrails

- Treat native workflow and durable repository data as source of truth; AG-UI events are additive projections.
- Do not widen the public stream surface to include applicant PII, financial inputs, checkpoint payloads, or secrets.
- Preserve ordering expectations for run start, progress, checkpointed interruption, resume, terminal output, and failures.
- Keep CopilotKit as a separate allowlisted explanation surface; AG-UI changes must not silently broaden assistant data access.

## Required verification

1. Validate `backend/tests/test_agui.py`.
2. Validate `backend/tests/test_hosted_relay.py` and `backend/tests/test_hosted_telemetry_correlation.py` when hosted relay or telemetry semantics change.
3. Validate `frontend/tests/e2e/underwriting.spec.ts`.
4. Validate docs parity in `docs/design/schema-io-telemetry.md` and `docs/design/e2e-rubric.md`.
