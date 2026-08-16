# Engineering Operating Model

## Purpose

This is the canonical delivery contract for the LangGraph migration target.
Architecture intent and business rules come from the team, reference docs and
approved learnings constrain implementation, and validation gates provide the
only acceptable release evidence.

## Runtime policy

This lane has three supported execution surfaces:

1. **Local full stack**: React, FastAPI, native SSE, LangGraph, and PostgreSQL.
   This remains the authoritative browser contract surface.
2. **Public Foundry hosted agent**: the hosted container runs the same shared
   LangGraph workflow through Responses 2.0.
3. **Public hosted UI and wrapper**: an external frontend proxies same-origin
   API traffic to an internal FastAPI wrapper, which uses managed identity to
   invoke Foundry and replays durable PostgreSQL history to the browser.

Historical MAF reference material is migration provenance only. It does not
constitute current deployment proof.

## Non-negotiable contracts

- One business workflow path implemented as one shared LangGraph `StateGraph`.
- Native HITL uses `interrupt()` and `Command(resume=...)`.
- Only one unresolved interrupt may exist per thread. New normal turns are
  rejected or explicitly deferred until that interrupt is resolved.
- Stable browser event types remain:
  `workflow.stage`, `tool.call`, `checkpoint.created`, `hitl.request`,
  `hitl.response`, and `workflow.output`.
- `AsyncPostgresSaver` owns graph checkpoint durability; separate audit
  projections own history, replay, approvals, and evidence.
- The native checkpoint is the workflow-state source of truth. The approval
  UUID table is an idempotent audit projection that may be reconciled from
  graph state at startup or on demand.
- Audit projections must not duplicate authoritative action, order, or amount
  state.
- `AsyncPostgresSaver` pooling is an application-lifetime singleton resource,
  not a per-request dependency.
- `checkpoint.created` and `hitl.request` are emitted in approval preparation,
  not replayed from the resumed interrupt node.
- Production schema DDL stays administrator-owned and production runtime uses
  `DB_SCHEMA_MANAGED_EXTERNALLY=true`.
- Hosted runtime secrets resolve only through the deterministic project
  `CustomKeys` connection placeholder; resolved URLs must not appear in hosted
  metadata or evidence.
- Foundry hosting remains Responses-native and browser access remains
  same-origin through the frontend proxy.
- AG-UI and CopilotKit remain optional, read-only, selected-thread, redacted
  views.
- Application Insights is the required telemetry backend.
  **LangSmith is not required.**
- Evaluation must use only fresh hosted E2E evidence after the configured trace
  age and must report explicit completion.
- Release evidence must be fresh, window scoped, secret free, and tied to one
  release report plus a reviewed ledger entry.

## Delivery and validation

| Change | Required local gates | Required hosted gates |
| --- | --- | --- |
| Application behavior | `make test`, `make eval-backend`, `make test-e2e` | Only if hosted behavior or release evidence changes |
| HITL, persistence, or contracts | Local gates plus focused resume/idempotency checks | Fresh low-risk, high-risk approval, and damaged-item HITL hosted E2E |
| Foundry runtime, IaC, or release scripts | Local gates plus script, profile, and packaging validation | Preview, readiness, app-only deploy, verify, smoke, hosted E2E, telemetry, evaluation, final evidence |
| Documentation only | Link and terminology checks | None unless deployment instructions or evidence policy changed |

GitHub Actions remains credential-free CI only. Authenticated Azure mutation
and release execution are local operator actions.

## Evidence handoff

For each deployment-affecting change, record in
[issues-changes-fixes.md](issues-changes-fixes.md):

- changed surfaces and intent
- validation gates run
- database readiness and least-privilege result
- package-feed and hosted source-sync compliance
- immutable image verification
- same-origin proxy JSON or SSE verification
- fresh hosted E2E scope
- trace-age-aware evaluation result
- Application Insights correlation and exception result
- release timing and evidence-integrity notes
- any checkpoint-to-approval reconciliation behavior exercised

## Baseline scenarios

- `ORD-1001`: low risk, completes without HITL
- `ORD-1009`: high amount, pauses for HITL and completes after approval
- damaged item: pauses for HITL and resolves after approval or escalates after
  rejection
