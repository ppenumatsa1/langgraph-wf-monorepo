# Engineering Operating Model

## Purpose

This is the canonical delivery contract for the private LangGraph lane.
Architecture intent and business rules come from the team, reference
documentation constrains implementation, and validation gates provide the only
acceptable release evidence.

This document describes required behavior; it does not claim a live Azure
deployment or successful hosted run.

## Runtime policy

This lane has three supported execution surfaces:

1. **Local full stack**: React, FastAPI, native SSE, LangGraph, and PostgreSQL.
   This remains the authoritative browser contract surface.
2. **Private Foundry hosted agent**: the private hosted container runs the same
   shared LangGraph workflow through Responses 2.0.
3. **External frontend and internal wrapper**: the frontend proxies same-origin
   API traffic to an internal FastAPI wrapper, which uses managed identity to
   invoke private Foundry and private PostgreSQL.

Private ACR supplies immutable images. A private runner performs noninteractive
validation, packaging, and approved Azure mutation. Application Insights is
the required observability backend; LangSmith is not required.

## Network policy

The hosted lane uses an isolated primary BYO VNet plus a small globally peered
Search private-endpoint VNet:

| Reservation | CIDR | Policy |
| --- | --- | --- |
| BYO VNet | `10.74.0.0/16` | One isolated lane address space |
| Foundry integration | `10.76.0.0/24` | Private Foundry integration |
| Foundry dependency endpoints | `10.76.1.0/24` | Hosted-compute dependency access |
| Container Apps | `10.74.2.0/23` | External frontend and internal wrapper |
| Private endpoints | `10.74.4.0/24` | Foundry, PostgreSQL, and approved application-side services |
| Private runner | `10.74.5.0/27` | Noninteractive automation |
| Search private endpoint | `10.75.0.0/27` | Same-region private endpoint for the `westus3` Search service |

Only the frontend has external ingress. The wrapper, Foundry, PostgreSQL, ACR,
and runner are private. Private DNS zones/links, endpoint approval, managed
identity, and least-privilege RBAC are mandatory prerequisites.

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
  graph state.
- Audit projections must not duplicate authoritative action, order, or amount
  state.
- `AsyncPostgresSaver` pooling is an application-lifetime singleton resource,
  not a per-request dependency. Because each wrapper replica and Foundry
  session is a separate application process, both persistence pools must be
  bounded and shrink to zero idle connections in hosted execution.
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
- Evaluation uses fresh hosted E2E evidence after the configured trace age and
  reports explicit completion.
- Release evidence is fresh, window scoped, secret free, and tied to one
  release report plus a reviewed ledger entry.
- Deployment automation is noninteractive and fails closed on unexpected
  targets, destructive plans, missing private DNS, endpoint approval, RBAC,
  readiness, or secret-free evidence.
- Deployment safety gates do not replace business HITL.

## Delivery and validation

| Change | Required local gates | Required private-hosted gates |
| --- | --- | --- |
| Application behavior | `make test`, `make eval-backend`, `make test-e2e` | Only if hosted behavior or release evidence changes |
| HITL, persistence, or contracts | Local gates plus focused resume/idempotency checks | Fresh low-risk, approval/resume, and damaged-item HITL E2E |
| Foundry runtime, IaC, or release scripts | Local gates plus script, profile, and packaging validation | Preview, private readiness, app-only deploy, verify, smoke, E2E, telemetry, evaluation, final evidence |
| Documentation or skills only | Existing frontmatter/link/terminology checks | None; no live claim |

GitHub Actions remains credential-free CI only. Authenticated Azure mutation
and release execution occur from the private runner; CI must not mutate Azure.

## Evidence handoff

For each deployment-affecting change, record in
[issues-changes-fixes.md](issues-changes-fixes.md):

- changed surfaces and intent;
- validation gates run;
- private DNS, endpoint, identity/RBAC, and service readiness result;
- database readiness and least-privilege result;
- package-feed and hosted source-sync compliance;
- immutable image verification;
- same-origin proxy JSON or SSE verification;
- fresh hosted E2E scope;
- trace-age-aware evaluation result;
- Application Insights correlation and exception result;
- release timing and evidence-integrity notes; and
- any checkpoint-to-approval reconciliation behavior exercised.

## Baseline scenarios

- `ORD-1001`: low risk, completes without HITL
- `ORD-1009`: high amount, pauses for HITL and completes after approval
- damaged item: pauses for HITL and resolves after approval or escalates after
  rejection
