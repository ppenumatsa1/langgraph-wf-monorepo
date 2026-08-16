# Agents Guide

This file defines the approved documentation contract for coding agents working
in this repository.

## Project context

- Backend: FastAPI plus one shared LangGraph `StateGraph` business workflow.
  Do not introduce a second orchestration path.
- Hosted runtime: Azure AI Foundry Responses 2.0 container hosting wraps the
  same business workflow; the hosted entrypoint stays a thin host around the
  shared application service.
- Public browser delivery: external frontend Container App -> same-origin `/api`
  proxy -> internal FastAPI wrapper -> Foundry Responses -> shared PostgreSQL.
- Durable HITL: LangGraph native `interrupt()` pauses the graph and
  `Command(resume=...)` resumes it. PostgreSQL stores graph checkpoints through
  `AsyncPostgresSaver`; separate audit projections store runs, events,
  approvals, transcripts, and release evidence.
- Only one unresolved interrupt may exist per thread. While that interrupt is
  pending, reject or explicitly defer new normal user turns rather than
  creating parallel graph progress.
- Native checkpoint state is the source of truth for workflow state. The
  approval UUID table is an idempotent audit projection and reconciliation
  aid, not a duplicate source of authoritative action, order, or amount state.
- The `AsyncPostgresSaver` connection pool must be created once per app
  lifetime and reused across requests.
- PostgreSQL schema DDL is administrator-owned. Production runtimes set
  `DB_SCHEMA_MANAGED_EXTERNALLY=true`; the runtime credential remains limited
  to required DML and sequence usage.
- Stable browser event contract:
  - `workflow.stage`
  - `tool.call`
  - `checkpoint.created`
  - `hitl.request`
  - `hitl.response`
  - `workflow.output`
- AG-UI and CopilotKit remain optional, read-only, redacted selected-thread
  projections. They must not start, resume, approve, or reject a workflow.
- The browser must never call Foundry, MCP, or RAG services directly and must
  never receive raw order data, policy payloads, retrieval content, tool
  arguments or results, prompts, model output, checkpoint state, credentials,
  or secrets.
- Observability is Application Insights only. Preserve workflow, model,
  Foundry, and HITL correlation. **Do not require LangSmith.**

Historical Microsoft Agent Framework names and directories are migration
provenance only. Do not preserve them as the architectural end state except
when explicitly documenting the migration history.

## Agent change policy

1. Keep changes focused on the requested scope.
2. Use one shared LangGraph workflow path. Do not create a parallel deterministic
   orchestrator, assistant-only path, or hosted-only workflow.
3. Preserve the stable API and SSE contract unless the same change set also
   updates every dependent frontend, test, and documentation surface.
4. If HITL logic changes, update docs and tests in the same change set.
5. Keep privacy and audit boundaries explicit:
   - checkpointer state is for graph durability;
   - audit projections are for browser history, SSE replay, approvals,
     evidence, and operations;
   - projections must not duplicate authoritative action, order, or amount
     state already owned by the graph checkpoint;
   - selected-thread projections are allowlisted and redacted.
6. Emit `checkpoint.created` and `hitl.request` during approval preparation,
   before the interrupt is replayed or resumed. Do not synthesize them from the
   replayed interrupt node.
7. Keep release controls intact:
   - bootstrap creates the full lane;
   - reuse is non-mutating;
   - hosted images deploy by immutable digest;
   - Python and npm package acquisition stays on approved Microsoft feeds;
   - Foundry runtime secrets resolve through the deterministic project
     `CustomKeys` connection placeholder rather than a resolved URL in source
     or metadata.
8. Keep Application Insights request filtering intact for health and SSE paths
   so long-lived requests do not hide workflow signal.
9. Treat same-origin proxy JSON failures as release blockers. API routes must
   not fall back to HTML or other unexpected content types.

## Required verification before completing work

Run and report:

- `make test`
- `make eval-backend`
- `make eval-foundry`
- `make test-e2e`
- `./scripts/skills/design-review-skill.sh`

For deployment or hosted packaging changes, also run:

- `make test-deployment-profile`
- `make test-scripts`
- `make foundry-iac-build`
- `make foundry-package`

If a suite cannot run because of missing runtime dependencies, report the exact
blocker and the command required to unblock it.

## Repository skills and guidance

- Use `design-review` as the final deterministic local review gate.
- Use `docs-sync` for documentation updates after code or hosting changes.
- Use `backend-boundary-review` to preserve API, application, runtime, and
  infrastructure separation.
- Use `local-validation` for local unit, integration, and E2E gates.
- Use `quick-validation` only for low-risk app-only redeployments.
- Use `iac-review`, `azure-validation`, `azure-deployment`, and
  `azure-telemetry-validation` only when the task actually reaches those
  surfaces.

## HITL baseline scenarios

Use these contract scenarios:

- `ORD-1001` late delivery -> no `hitl.request`
- `ORD-1009` delayed high amount -> `hitl.request`
- damaged item message -> `hitl.request`

Approval completes the workflow. Rejection escalates it. Duplicate responses
must remain idempotent.

## Documentation update contract

When architecture, runtime, or execution policy changes, update these docs in
the same PR:

- `README.md`
- `agents.md`
- `docs/design/architecture.md`
- `docs/design/userflow.md`
- `docs/design/hitl-approval-conditions.md`
- `docs/design/schema-io-telemetry.md`
- `docs/design/engineering-operating-model.md`
- `docs/design/deployment-flow.md`
- `docs/design/projectstructure.md`
- `docs/design/techstack.md`
- `docs/design/issues-changes-fixes.md`
- `docs/manual-testing.md`
