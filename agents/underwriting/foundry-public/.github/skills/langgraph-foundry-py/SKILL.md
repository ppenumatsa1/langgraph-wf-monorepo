---
name: langgraph-foundry-py
description: Maintain this underwriting service's LangGraph + Foundry hosted-agent runtime, including parallel check execution, native PostgreSQL checkpointing, durable event projection, and Application Insights correlation.
---

# LangGraph + Foundry for Underwriting

Use this repository-owned skill for the application's single LangGraph workflow path.

## Runtime and ownership

- `backend/app/langgraph/*` is the target namespace for graph composition, state, nodes, prompts, tools, and runtime helpers.
- `backend/foundry/main.py` owns the Responses-native hosted-agent entrypoint. Keep one hosted runtime path built on Foundry Responses 2.0 hosting.
- `backend/app/api/v1/routes/*` owns HTTP, AG-UI, and CopilotKit route boundaries only.
- `backend/app/api/v1/schemas/*` owns request and response contracts.
- `backend/app/modules/underwriting/*` owns service seams, deterministic decision policy, redacted selected-run projection logic, and durable event projection.
- `backend/app/infrastructure/*` owns PostgreSQL, idempotency, telemetry helpers, and Foundry wrapper clients.

Legacy `backend/app/maf/*` directories may remain during migration, but they are provenance only and must not remain as a parallel workflow path.

## Graph and hosting patterns

- Keep one compiled LangGraph workflow path.
- Preserve the underwriting graph shape: `init_context`, parallel risk/credit/medical/driving checks, `fan_in_aggregator`, deterministic `final_decision`, and optional rationale generation.
- Keep Foundry hosting Responses-native.
- Prefer one repository-owned Foundry project/model configuration contract.
- Prefer streamed graph outputs plus durable projections for AG-UI updates instead of bypassing the graph runtime.

## Durability and recovery

- Use the native PostgreSQL LangGraph checkpointer for authoritative resume state.
- Preserve stable `workflow_run_id` to thread identity mapping and checkpoint identifiers needed for resume and audit.
- Production DDL remains administrator-owned. When `DB_SCHEMA_MANAGED_EXTERNALLY=true`, runtime code must not create or mutate schema objects to satisfy startup or checkpoint initialization.
- Keep side-effecting persistence idempotent. Retry model or read operations only; do not blindly retry writes after uncertain transaction outcomes.
- Checkpoint payloads may retain only the minimum operational PII needed for correct resume and audit. Keep raw checkpoint data out of browser projections, logs, telemetry summaries, and selected-run assistant surfaces.

## Browser and event contracts

- Preserve durable REST routes for runs, state, events, checkpoints, and history.
- Preserve AG-UI streaming through `POST /api/v1/underwriting/ag-ui` with the frontend-consumed `CUSTOM` / `underwriting.event` envelope.
- Preserve stable durable event names consumed by the UI and tests: `workflow_start`, `retry_attempt`, `retry_backoff`, `retry_exhausted`, `check_completed`, `fan_in_result_received`, `final_decision`, `workflow_completed`, `workflow_crashed`, `resume_requested`, `resume_completed`, and `idempotency_skip`.
- Keep AG-UI and CopilotKit additive and read only. They must never become a second runtime path.
- Keep the selected-run projection allowlisted to safe run metadata and categorical final decision only.

## Telemetry

- Application Insights is the required observability backend.
- Correlate `workflow.run_id`, retry attempts, checkpoint identifiers, executor names, and final decision spans across start and resume.
- Emit once-only retry, checkpoint, idempotency, and terminal workflow events from durable orchestration code rather than replay-prone node bodies.

## Required verification

1. `make test`
2. `make quality`
3. `make test-e2e` when UI, API, AG-UI, CopilotKit, or durable-history contracts change
4. `make foundry-eval` for hosted runtime, prompt, evaluator, or telemetry changes

## Current reference material

- LangGraph overview: https://docs.langchain.com/oss/python/langgraph/overview
- LangGraph checkpointers: https://docs.langchain.com/oss/python/langgraph/checkpointers
- LangGraph persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- LangGraph streaming: https://docs.langchain.com/oss/python/langgraph/streaming
- Foundry hosted LangGraph agents: https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/langchain-hosted-agents
- LangGraph with Foundry Agent Service: https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/langchain-agents

