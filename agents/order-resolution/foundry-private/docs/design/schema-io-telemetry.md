# Schema, I/O, and Telemetry

## Chat run request

```json
{
  "message": "Order ORD-1009 is delayed by 5 days.",
  "thread_id": "optional",
  "session_id": "optional",
  "customer_id": "cust-demo"
}
```

## Native SSE event envelope

```json
{
  "id": "uuid",
  "type": "workflow.stage | tool.call | checkpoint.created | hitl.request | hitl.response | workflow.output",
  "thread_id": "uuid",
  "timestamp": "2026-08-16T00:00:00Z",
  "payload": {}
}
```

These event names are stable across local execution and the private Foundry
hosted runtime.

## Rich event envelope

The primary contract remains `GET /api/chat/stream/{thread_id}`. The additive
rich stream at `GET /api/chat/stream/{thread_id}/rich` may wrap the same native
events like this:

```json
{
  "type": "workflow.rich",
  "version": "ag-ui-compatible.v1",
  "id": "native-event-id:rich:1",
  "thread_id": "uuid",
  "timestamp": "2026-08-16T00:00:00Z",
  "source": "langgraph-order-resolution",
  "native_event": {},
  "events": []
}
```

Rich events are additive only. They must not rename or replace native event
types.

## Redacted selected-thread projections

The optional selected-thread surfaces are:

- `GET /api/chat/stream/{thread_id}/ag-ui`
- `POST /api/copilotkit`

They expose only:

- safe lifecycle labels
- safe tool categories and completion state
- opaque valid checkpoint identifiers
- approval state
- generic terminal or error text

They never expose:

- raw order or customer data
- policy payloads or retrieval content
- MCP/RAG requests or results
- prompts or raw model output
- checkpointer payloads
- credentials or secrets

CopilotKit here means `@copilotkit/react-core`, not the GitHub Copilot SDK.

## HITL response request

```json
{
  "checkpoint_id": "uuid",
  "decision": "approve",
  "reviewer": "ops-analyst",
  "comments": "optional"
}
```

## Persistence model

- An app-lifetime singleton `AsyncPostgresSaver` pool owns thread-scoped graph
  checkpoint persistence for LangGraph execution and resume.
- "App lifetime" is process-local: each wrapper replica and retained Foundry
  session has separate synchronous audit and asynchronous checkpoint pools.
  Production configuration uses a zero idle floor, short idle lifetime,
  bounded maxima, and distinct PostgreSQL application names.
- Separate application audit projections own workflow runs, workflow events,
  approvals, transcripts, idempotency records, and release-evidence metadata.
- The native checkpoint is the workflow-state source of truth.
- The approval UUID table is an idempotent audit projection for pending and
  resolved approval records.
- Startup and on-demand reconciliation must rebuild or repair approval
  projection rows from authoritative graph state when the audit view is stale
  or incomplete.
- Audit projections must not duplicate authoritative action, order, or amount
  state already stored in the checkpoint.

This separation is required: the checkpointer is not the browser history model,
and the audit projection is not the source of graph resume state.

## Event timing semantics

- `checkpoint.created` and `hitl.request` are emitted during approval
  preparation, after durable checkpoint persistence succeeds and before the
  interrupt is surfaced to the caller.
- Resume processing emits `hitl.response` and terminal workflow events, but
  must not replay or synthesize a second `checkpoint.created` or
  `hitl.request`.

## Checkpoint privacy and retention

- Native checkpoint tables may contain resume-critical PII, including order or
  customer identifiers needed to continue the workflow.
- Treat checkpoint rows as restricted operational data: minimize exports,
  limit read access, define explicit retention, and avoid projecting raw
  checkpoint payloads into browser-visible surfaces or general audit summaries.

## Telemetry conventions

- Business spans:
  - `workflow.run`
  - `workflow.hitl_waiting`
  - `workflow.hitl_resume`
  - `workflow.resolution_submit`
- Correlation attributes:
  - `workflow.thread_id`
  - `workflow.run_id`
  - `workflow_run_id` where the durable event payload is projected
  - `session_id`
  - `event_id`
  - `checkpoint_id`

## Application Insights wiring

- Application Insights is the required telemetry sink.
- LangSmith is not required for runtime, release, or evaluation gating.
- Hosted telemetry is emitted by the internal wrapper and private Foundry
  runtime; it must not require browser access to private services.
- Correlate hosted records to the private release window and workflow
  identifiers. A telemetry row count alone is not proof of private DNS,
  endpoint, identity, or deployment readiness.
- FastAPI health (`/health`, `/api/health`) and chat SSE request spans may be
  excluded from request telemetry so probes and long-lived streams do not
  obscure workflow signal.
- Workflow, Foundry invocation, model, and HITL correlation remain the
  required operational signal.

## Trace-age-aware evaluation

- Hosted evaluation must use only fresh hosted-E2E conversations.
- Evaluation must wait for the configured minimum telemetry and trace
  materialization age before scoring HITL conversations.
- Evaluation evidence is valid only when the run reports an explicit completed
  status.

## Operational checks

- Verify same-origin API routes return JSON or SSE as expected; HTML or other
  content-type fallbacks are proxy failures, not workflow evidence.
- Query Application Insights using workflow and checkpoint correlation first;
  do not treat newest-first portal lists as authoritative release evidence.
