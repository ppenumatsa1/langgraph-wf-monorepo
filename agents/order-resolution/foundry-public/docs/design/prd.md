# PRD - Customer Order Resolution LangGraph Workflow

## Objective

Build a demo-ready order-resolution workflow on **one shared LangGraph
StateGraph** while preserving the existing business behavior, browser
contracts, privacy boundaries, and public Foundry hosting model.

## Core features

- Sequential business flow: triage -> policy retrieval -> resolution ->
  explanation or follow-up.
- Native LangGraph human approval with `interrupt()` and
  `Command(resume=...)`.
- Durable PostgreSQL checkpointing through `AsyncPostgresSaver`.
- Separate PostgreSQL audit projections for workflow runs, events, approvals,
  transcripts, and release evidence.
- Stable FastAPI and SSE contracts for the browser and Playwright suites.
- Same-origin public wrapper: the browser calls `/api`; only the backend uses
  managed identity to invoke Foundry Responses.
- Optional MCP integration and optional RAG integration behind backend-only
  ports.
- Application Insights-only observability and release evaluation evidence.
- Optional AG-UI and CopilotKit selected-thread projections that remain
  redacted and read only.

## Non-goals (v1)

- Parallel or branching business workflows.
- Browser-direct access to Foundry, MCP, RAG, or PostgreSQL.
- Production auth redesign.
- LangSmith adoption as a release prerequisite.
- Reusing historical MAF deployment identifiers as LangGraph proof.

## Acceptance criteria

1. One customer request drives all business stages through one LangGraph graph.
2. The workflow emits the stable native event names without breaking frontend
   or test consumers.
3. HITL pauses use native interrupts and durable PostgreSQL checkpointing.
4. Approval and rejection resume from the saved checkpoint state with one
   idempotent outcome.
5. Low-risk cases complete without HITL.
6. Public hosting keeps the browser on a same-origin API/SSE contract while
   the wrapper delegates to Foundry Responses 2.0.
7. Telemetry exports to Application Insights with no LangSmith requirement.
8. Release validation enforces least-privilege PostgreSQL access, immutable
   packaging, trace-age-aware evaluation, and evidence integrity.

## Delivery contract

Implementation authority and release evidence expectations are defined in
[engineering-operating-model.md](engineering-operating-model.md). Imported MAF
documents are migration provenance only.
