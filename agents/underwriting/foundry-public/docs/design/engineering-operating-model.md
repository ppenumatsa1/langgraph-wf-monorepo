# Engineering Operating Model

## Purpose

This is the canonical delivery contract for the underwriting LangGraph migration target. Business rules define the underwriting behavior, reference migration learnings constrain implementation, and validation gates provide the only acceptable release evidence.

## Runtime policy

This lane has three supported execution surfaces:

1. **Local full stack**: React, FastAPI, AG-UI, and PostgreSQL. This remains the authoritative browser contract surface.
2. **Public Foundry hosted agent**: the hosted container runs the same shared underwriting business flow through Responses 2.0.
3. **Public hosted UI and wrapper**: an external frontend proxies same-origin API traffic to an internal FastAPI wrapper, which invokes Foundry and replays durable PostgreSQL history to the browser.

Historical MAF reference material is migration provenance only. It does not constitute current deployment proof.

## Non-negotiable contracts

- One business workflow path implemented as one shared LangGraph `StateGraph`.
- Deterministic underwriting decision stays authoritative before rationale generation.
- Risk, credit, medical, and driving checks remain visible as four fan-in contributors.
- Native PostgreSQL checkpointer state owns workflow resume authority.
- Separate audit projections own history, replay, results, checkpoint summaries, idempotency evidence, and release evidence.
- Stable browser-facing surfaces remain `POST /api/v1/underwriting/runs`, `POST /api/v1/underwriting/runs/{run_id}/resume`, durable read-model routes, `POST /api/v1/underwriting/ag-ui`, and CopilotKit discovery or run routes.
- AG-UI and CopilotKit remain optional, read-only, selected-run, redacted views.
- Same-origin `/api` and `/backend-health` behavior is required; HTML or other unexpected content types on API routes are release blockers.
- The browser never receives Foundry or PostgreSQL credentials.
- Production schema DDL stays administrator-owned and production runtime uses `DB_SCHEMA_MANAGED_EXTERNALLY=true`.
- Hosted runtime secrets resolve only through the deterministic project `CustomKeys` connection placeholder; resolved URLs must not appear in hosted metadata or evidence.
- Application Insights is the required telemetry backend.
- Release evidence must be fresh, window scoped, secret free, and recorded in `docs/design/issues-changes-fixes.md`.

## Delivery and validation

| Change | Required local gates | Required hosted gates |
| --- | --- | --- |
| Frontend, docs, or instruction updates | `make quality` when UI changed, `make test-e2e` when operator behavior changed | None unless deployment instructions or hosted evidence policy changed |
| Application behavior | `make test`, `make quality`, `make test-e2e` | Only if hosted behavior or release evidence changed |
| Workflow, retry, persistence, or crash or resume | Local gates plus targeted local scenario verification as needed | Fresh hosted smoke covering the same scenario class when release behavior changed |
| Foundry runtime, IaC, or release scripts | Local gates plus checked-in script review | `make foundry-smoke`, `make foundry-eval`, telemetry correlation, verification, and evidence aggregation |

GitHub Actions remains credential-free CI only. Authenticated Azure mutation and release execution are local operator actions.

## Evidence handoff

For each deployment-affecting change, record in
[issues-changes-fixes.md](issues-changes-fixes.md):

- changed surfaces and intent
- validation gates run
- package-feed and hosted source-sync compliance
- same-origin proxy JSON or SSE verification
- fresh hosted E2E scope
- report-only evaluation result
- Application Insights correlation result
- any privacy or release-evidence deferrals

## Baseline scenarios

- Happy path: low-risk application completes with one deterministic result and rationale.
- Retry path: one injected retryable check failure records retry evidence and completes once.
- Crash or resume path: a controlled crash resumes from the latest PostgreSQL-backed checkpoint and completes without duplicate writes.
- Privacy path: selected-run assistant surfaces only allowlisted run metadata and categorical decision state.
