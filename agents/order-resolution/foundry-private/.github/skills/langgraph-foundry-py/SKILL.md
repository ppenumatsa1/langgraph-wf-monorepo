---
name: langgraph-foundry-py
description: Maintain this order-resolution service's LangGraph + private Foundry runtime. Use for graph composition, langchain-azure-ai hosting, native Postgres checkpointers, interrupt/resume HITL flows, durable event projection, and workflow telemetry.
---

# LangGraph + Foundry for Order Resolution

Use this repository-owned skill for the application's single LangGraph workflow path.

## Runtime and ownership

- `backend/app/langgraph/*` owns graph composition, nodes, tools, prompts, and runtime helpers.
- `backend/foundry/main.py` owns the Responses-native hosted-agent entrypoint. Keep one hosted runtime path built on `langchain_azure_ai.agents.hosting.ResponsesHostServer`.
- `backend/app/api/v1/routers/*` owns HTTP/SSE routes only.
- `backend/app/api/v1/schemas/*` owns API contracts.
- `backend/app/modules/order_resolution/*` owns service/domain seams, HITL policy, and durable event projection.
- `backend/app/infrastructure/*` owns adapters for persistence, events, RAG, and external integrations.

## Graph and private hosting patterns

- Keep one compiled LangGraph workflow path. Do not add a second orchestration path in the wrapper, frontend, or assistant bridge.
- Keep Foundry hosting Responses-native behind the private network. Do not
  expose the Foundry endpoint to the browser or reintroduce legacy invocations
  adapters unless the task explicitly requires a new protocol and updates
  tests/contracts together.
- The external frontend may be public, but it talks only to the internal
  FastAPI wrapper through same-origin `/api`. The wrapper calls private Foundry
  and private PostgreSQL; private ACR and a private runner provide delivery
  and automation.
- The application VNet is `10.74.0.0/16`; Foundry uses the separate
  `10.76.0.0/16` VNet with integration subnet `10.76.0.0/24` and dependency
  endpoint subnet `10.76.1.0/24`. Container Apps use `10.74.2.0/23`,
  application private endpoints use `10.74.4.0/24`, and the runner uses
  `10.74.5.0/27`. Private DNS and managed-identity connectivity are
  prerequisites, not fallbacks.
- Prefer `DefaultAzureCredential` and one repository-owned Foundry project/model configuration contract. If configuration names change, update bootstrap, tests, and deployment assets together rather than supporting parallel env-var sets.
- Prefer LangGraph event streaming for runtime projections and telemetry. Use streamed graph outputs to derive stable SSE events instead of bypassing the graph runtime.

## Durable HITL and checkpointing

- Use the native Postgres checkpointer for LangGraph durability. Keep stable `thread_id` usage and preserve checkpoint identifiers/namespaces needed for resume and audit.
- Production DDL remains administrator-owned. When `DB_SCHEMA_MANAGED_EXTERNALLY=true`, runtime code must not create or mutate schema objects just to satisfy startup or checkpoint initialization.
- Apply admission control before creating a new interrupt or approval record. If a thread already has a pending interrupt, reconcile and resume or reject the duplicate request instead of minting a second pending checkpoint.
- Enforce at most one pending interrupt per thread. Approval and resume paths must prove they are operating on the currently pending checkpoint for that thread.
- Pause work with `interrupt(...)` and resume with `Command(resume=...)` on the same thread. Preserve the explicit approval request/response boundary; do not auto-approve, auto-resume, or bypass persisted review state.
- Treat the native LangGraph checkpoint as the source of truth for paused graph state. Approval rows, inbox records, and UI summaries are idempotent derived projections and must stay reconstructible from checkpoint-backed state.
- Reconcile graph state before resume and before emitting final business outcomes: compare the pending checkpoint, the idempotent approval projection, and the requested action, then continue only when they agree.
- Do not duplicate authoritative business state across checkpoint tables, approval projections, workflow summaries, or UI caches. Derived records may summarize status, but the checkpoint-backed graph state remains authoritative.
- Keep side-effecting resolution submission idempotent. Retry model/read operations only; do not blindly retry writes after uncertain transaction outcomes.
- Checkpoint payloads may retain only the minimum operational PII needed for correct resume and audit. Keep PII out of projections, logs, telemetry summaries, and selected-thread assistant surfaces unless an explicit contract requires a redacted form.

## Telemetry and event contracts

- Preserve stable native SSE event types: `workflow.stage`, `tool.call`, `checkpoint.created`, `hitl.request`, `hitl.response`, and `workflow.output`.
- Keep additive AG-UI/CopilotKit projections derived from durable workflow state; they must never become a second runtime path.
- Correlate `workflow.thread_id`, `workflow.run_id`, `checkpoint_id`, and approval decisions across graph execution and resume.
- Keep LangGraph node/tool/checkpoint spans as the operational signal and restore trace context across interrupt/resume so approval spans stay attached to the originating workflow operation.
- Emit once-only approval, checkpoint, and terminal workflow events from orchestration code that runs after graph-state reconciliation, not from replayable interrupt node bodies that may execute again on resume.
- Use Application Insights for runtime, Foundry, model, and HITL correlation.
  LangSmith is not required and must not become a release gate.

## Automation boundary

- Infrastructure previews and releases run from the private runner without
  prompts, confirmation tokens, or interactive secret entry.
- Fail closed on delete/replace plans, target drift, missing private DNS or
  endpoint approval, missing identity/RBAC, readiness failures, or
  secret-bearing evidence.
- These deployment gates do not replace business approval. Preserve native
  `interrupt()` and `Command(resume=...)` for risky order resolutions.

## Required verification

1. `make test`
2. `make eval-backend`
3. `make foundry-private-eval` for private hosted runtime, prompt, evaluator,
   or telemetry changes
4. `make test-e2e` when UI, API, streaming, or HITL contracts change

## Current reference material

- LangGraph checkpointers: https://docs.langchain.com/oss/python/langgraph/checkpointers
- LangGraph interrupts: https://docs.langchain.com/oss/python/langgraph/interrupts
- LangGraph streaming: https://docs.langchain.com/oss/python/langgraph/streaming
- Foundry hosted LangGraph agents: https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/langchain-hosted-agents
- LangGraph with Foundry Agent Service: https://learn.microsoft.com/en-us/azure/foundry/how-to/develop/langchain-agents
