---
name: ag-ui-streaming-fastapi-py
description: Implement and review Order Resolution's additive FastAPI AG-UI and CopilotKit projections of durable workflow events without changing the stable SSE contract.
---

# AG-UI Streaming for FastAPI (Order Resolution)

Use this skill when changing streaming APIs, event envelopes, the selected-thread assistant bridge, or backend-to-frontend event projection.

## Scope

- Stable and additive route entrypoints: `backend/app/api/v1/routers/*`
- Stream and bridge schemas: `backend/app/api/v1/schemas/*`
- Safe projection and durable-tail helpers:
  `backend/app/modules/order_resolution/agui.py` and
  `backend/app/modules/order_resolution/durable_events.py`
- Boundary coverage: `backend/tests/test_order_resolution_boundaries.py`

## Invariants

- Native workflow events and durable PostgreSQL projections remain the source of truth. Rich AG-UI and CopilotKit frames are additive views, never a replacement for the stable native SSE contract.
- Preserve the stable event types and their consumer behavior:
  `workflow.stage`, `tool.call`, `checkpoint.created`, `hitl.request`,
  `hitl.response`, and `workflow.output`.
- Retain the single LangGraph workflow path. The HTTP wrapper projects or relays durable state only; it must not create a second orchestration path.
- Preserve durable interrupt/resume behavior and event ordering. The external frontend receives a non-streaming initial wrapper dispatch, then polls durable state and subscribes to persisted-event SSE.
- Treat the checkpoint-backed graph state as the native source of truth. AG-UI, CopilotKit, approval summaries, and workflow history rows are derived projections only and must not become a second authoritative business-state store.
- Preserve one-pending-interrupt-per-thread semantics in any projected approval status. If a thread already has a pending interrupt, the bridge must surface that existing state instead of inventing another pending item.
- CopilotKit is the selected read-only assistant integration. It is not the GitHub Copilot SDK. `GET /api/copilotkit/info` (and `GET /api/copilotkit`) returns static discovery only. `POST /api/copilotkit` may select one existing `threadId` and expose only the allowlisted, redacted projection; it must not start work or honor supplied `runId`, messages, state, tools, context, forwarded props, credentials, or arbitrary thread data.
- Never project raw order or policy data, MCP/RAG results, tool arguments/results, prompts, model output, checkpoint payloads, credentials, or secrets. Keep external-browser -> internal-wrapper access and privacy boundaries intact.
- Keep checkpoint PII in the checkpoint path only when required for resume or audit. Browser-visible projections must use redacted summaries, validated identifiers, and minimal approval metadata.
- The selected-thread projection may emit only `RUN_STARTED`, safe `STEP_*`/`TOOL_CALL_*` frames, CUSTOM checkpoint/approval summaries with validated UUIDs and approved/rejected decisions, generic terminal/error text, and `RUN_FINISHED`. Do not use the existing `/rich` native-event envelope as a redacted assistant stream.
- Emit projected terminal or approval events from reconciled durable state, not directly from replayable interrupt node execution where duplicates can appear after resume.

## Required verification

1. Run the affected backend projection and boundary tests, including `backend/tests/test_order_resolution_boundaries.py`.
2. Verify the static `GET /api/copilotkit/info` discovery response and that standard CopilotKit input is discarded rather than acted upon.
3. Run `make test-e2e` when a browser-visible stream or bridge contract changes.
4. Confirm an optional AG-UI/CopilotKit failure does not break native SSE or durable-history behavior.
