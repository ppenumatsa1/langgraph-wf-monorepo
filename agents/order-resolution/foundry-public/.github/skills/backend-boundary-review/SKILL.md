---
name: backend-boundary-review
description: Review backend changes for canonical module ownership, shim import safety, HITL coverage, and API/event contract stability.
---

# Backend Boundary Review Skill

Use this skill when reviewing backend changes for repository boundary compliance.

## Canonical ownership

- `backend/app/api/v1/routers/*` owns HTTP/SSE routes only.
- `backend/app/api/v1/schemas/*` owns API request/response contracts.
- `backend/app/modules/order_resolution/*` owns service/domain seams, policies, HITL, ports, and event projection.
- `backend/app/core/*` owns config, database, telemetry, and runtime composition.
- `backend/app/infrastructure/*` owns adapters, repositories, events, RAG, and MCP integrations.
- `backend/app/langgraph/*` owns LangGraph graphs, nodes, tools, prompts, and runtime helpers.

## Review guardrails

- Reject new canonical code that imports legacy compatibility shim paths.
- Tolerate existing compatibility shims only when they are unchanged or being safely removed.
- Keep API and emitted event contracts stable unless the task explicitly requests a contract change.
- Do not remove or rename event types without updating frontend consumers, tests, and docs.
- Require tests and eval cases for HITL behavior changes.
- Require updates to `docs/design/hitl-approval-conditions.md` when HITL decision logic changes.
- Require admission control for pending interrupts and reject designs that can create more than one active interrupt per thread.
- Treat checkpoint-backed LangGraph state as authoritative; approval summaries or workflow projections must be idempotent derived views, not duplicated business state stores.
- Require graph-state reconciliation before resume/finalization and reject code that emits once-only business events from replayable interrupt node bodies.
- Require singleton shared pool lifecycle for async database access; block new code that creates or tears down global pools inside request, node, or repository methods.
- Reject broad checkpoint payload fan-out. PII needed for resume may stay in the checkpoint path, but copied projections/logs/assistant payloads must remain redacted and minimal.

## Required checks

1. Inspect touched backend files for misplaced HTTP, schema, domain, core, infrastructure, or LangGraph runtime responsibilities.
2. Search changed imports for legacy shim paths and block newly introduced usage.
3. For HITL logic changes, verify matching updates in backend tests and/or `backend/.foundry/datasets/order-resolution-hosted-cases.jsonl`.
4. For API/event contract changes, verify the frontend, tests, and documentation were intentionally updated.
5. For checkpoint/approval changes, verify admission control, single-pending-interrupt semantics, graph-state reconciliation, and no duplicated authoritative business state.
6. For persistence changes, verify singleton pool lifecycle and that once-only workflow events are emitted outside replayed interrupt node code.

## Pass/fail behavior

- Pass when changes preserve canonical boundaries and required contract/HITL updates are present.
- Fail when new code crosses boundaries, imports legacy shims, or changes HITL/API/event behavior without matching tests, evals, and docs.
