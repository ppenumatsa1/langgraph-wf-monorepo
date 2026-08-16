# Backend - Shared LangGraph Order Resolution

FastAPI and the Foundry hosted Responses 2.0 entrypoint run the same typed
LangGraph `StateGraph` in `app/langgraph`. Stable HTTP schemas, routes, native
SSE event names, durable audit projections, MCP/RAG ports, redacted AG-UI and
CopilotKit projections, and the Foundry wrapper client remain unchanged.

## Database bootstrap

Runtime credentials never execute DDL. An administrator must bootstrap both the
application projection schema and LangGraph checkpoint tables:

```bash
python -m app.sql.bootstrap
psql "$DATABASE_URL" \
  -v runtime_role=order_resolution_runtime \
  -f app/sql/runtime_grants.sql
```

Production should set `DB_SCHEMA_MANAGED_EXTERNALLY=true` and
`VERIFY_DB_SCHEMA_ON_STARTUP=true`. The runtime needs DML/sequence access to the
application tables plus LangGraph's `checkpoints`, `checkpoint_blobs`,
`checkpoint_writes`, and `checkpoint_migrations` tables; it does not need
database/schema ownership or `CREATE`.

## Runtime

`RUNTIME_TARGET=local_langgraph` runs the graph directly in FastAPI.
`RUNTIME_TARGET=responses_wrapper` preserves the managed-identity wrapper that
dispatches to the hosted Responses endpoint.

When `FOUNDRY_PROJECTS_ENDPOINT` and
`FOUNDRY_MODEL_DEPLOYMENT_NAME` are configured, triage uses
`AzureAIOpenAIApiChatModel` with `DefaultAzureCredential`. Missing or failed
model configuration falls back deterministically inside the same graph. No
LangSmith tracing is configured. `LANGGRAPH_STRICT_MSGPACK=true` is enforced
before LangGraph checkpoint modules load.

The graph routes through explanation, triage, policy/MCP/RAG retrieval,
deterministic resolution, approval preparation, `interrupt()`,
`Command(resume=...)`, approved idempotent submission, rejection escalation,
and terminal output. Opaque API checkpoint UUIDs map to the LangGraph thread,
checkpoint namespace/ID, and interrupt ID in `workflow_interrupts`.

Only one unresolved interrupt is allowed per thread. A normal message sent to
an interrupted thread is rejected with HTTP `409`; the caller must submit the
approval decision instead. The approval-preparation node derives its opaque UUID
deterministically and records `checkpoint.created` / `hitl.request` in graph
state. The replayed interrupt node performs no pre-interrupt side effects.
Foundry free-text approval fallback is enabled only when that conversation has
a pending approval and the entire message is a strict confirmation such as
`Approve`, `Yes`, `Reject`, or `No`; `function_call_output` remains authoritative.

Local starts are guarded by a per-thread async lock. Supplying
`ChatRunRequest.idempotency_key` derives a stable run/thread identity and reuses
the durable dispatch record, so concurrent logical retries share the same
submission idempotency boundary.

LangGraph checkpoints are authoritative. `workflow_interrupts` and `approvals`
are repairable projections containing identifiers, status, reviewer audit, and
timestamps only; action, order, amount, prompt, tool, and policy state is loaded
from the graph checkpoint and validated during resume. Startup and on-demand
reconciliation use `aget_state()` to repair missing projections, replace stale
rows, finish crash-interrupted terminal projections, or fail an orphan whose
authoritative checkpoint is unavailable.

## Foundry hosted Responses 2.0

`foundry/main.py` uses `ResponsesAgentServerHost`. The Foundry conversation ID
is the LangGraph `thread_id`; initial text turns start the graph and
`function_call_output` turns approve or reject the mapped checkpoint. Package
with `Dockerfile.hosted`.

`ResponsesHostServer(compiled_graph)` was evaluated but is not used directly:
its default converter requires a `messages` state, exposes the internal
LangGraph interrupt ID, and invokes the graph outside the app-owned
workflow/event/approval reconciliation projections. The custom host adapter
retains those contracts while using the same compiled graph runtime.

The process owns one application-lifetime `AsyncConnectionPool` and
`AsyncPostgresSaver`; FastAPI closes it through lifespan shutdown and the hosted
handler initializes it lazily once.

`GET /api/chat/stream/{thread_id}` always replays and tails
`workflow_events`, in both local and wrapper modes. Clients may reconnect with a
`cursor=<timestamp>|<event-uuid>` assembled from the last event; native event
JSON and `: ping` heartbeat frames remain unchanged across process restarts.

## Checkpoint privacy and retention

Native LangGraph tables contain full workflow state, including user text,
customer/session identifiers, order and policy data, model context, and MCP/RAG
results. Restrict them to the runtime/admin roles, require encrypted PostgreSQL
connections and encrypted backups, and do not expose them through API
projections. `CHECKPOINT_RETENTION_DAYS` records the administrator-approved
retention policy and must be a positive integer when configured.

After the application schema and saver are bootstrapped, schedule the
administrator-owned retention statement:

```bash
psql "$DATABASE_URL" \
  -v retention_days="$CHECKPOINT_RETENTION_DAYS" \
  -f app/sql/checkpoint_retention.sql
```

It deletes native checkpoint state only for terminal workflows older than the
retention window and never deletes a thread with a pending/resuming interrupt.
Application audit/event projections remain subject to their separate retention
policy. PostgreSQL integration coverage executes the equivalent parameterized
pruning operation in `app.sql.retention` and verifies both deletion and pending
thread preservation.

## Contracts

- Stable events: `workflow.stage`, `tool.call`, `checkpoint.created`,
  `hitl.request`, `hitl.response`, `workflow.output`
- Audit/read projections: `workflow_runs`, `workflow_events`,
  `conversation_messages`, `workflow_interrupts`, `approvals`,
  `idempotency_keys`, `responses_dispatches`, `eval_runs`, `eval_results`
- Selected-thread AG-UI/CopilotKit surfaces remain read-only and redact order,
  policy, prompt, MCP/RAG, tool, checkpoint-state, credential, and model data.
- Application Insights export uses `APPLICATIONINSIGHTS_CONNECTION_STRING`;
  AgentServer configures the hosted OTel provider before Azure AI LangGraph
  auto-tracing attaches with node tracing enabled and content/state recording
  disabled. Application-authored attributes additionally honor
  `OTEL_RECORD_CONTENT`.

## Validation

```bash
ruff check app foundry evals tests
pytest -q
python -m evals.eval_runner
```

The deterministic evaluation writes runtime/checkpointer/dataset metadata to
`.foundry/results/report.json`.
