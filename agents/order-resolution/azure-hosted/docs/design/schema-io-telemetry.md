# Schema, I/O, and Telemetry

## Persistence

- Native LangGraph checkpoint tables: authoritative graph durability.
- Workflow/audit tables: runs, events, sessions, approvals, transcripts,
  idempotency, evaluations, and release projections.
- Administrator applies `backend/app/sql/schema.sql` and checkpointer setup.
- Runtime role has connect, schema usage, selected DML, and required sequence
  usage only; it has no schema or role creation permission.

## API and SSE

FastAPI remains the authoritative HTTP API. Nginx forwards `/api` without
response/request buffering, compression, or short read timeouts. The six
stable event types are unchanged. AG-UI/CopilotKit expose only allowlisted,
redacted selected-thread summaries.

## Telemetry

Correlation includes workflow thread/run IDs, checkpoint ID, approval decision,
model call, graph node, and tool call. Application Insights is the backend.
Prompts, raw model output, credentials, connection strings, checkpoint payloads,
and raw business records are excluded from evidence and default telemetry.
