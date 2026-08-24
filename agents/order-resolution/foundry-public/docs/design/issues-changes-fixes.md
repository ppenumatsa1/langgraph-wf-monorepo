# LangGraph Issues, Changes, and Adopted Learnings

## Evidence rule

This ledger records:

- adopted operational learnings from the imported MAF reference material,
- the current LangGraph documentation migration work, and
- future implementation and release proof requirements.

It does **not** copy old resource IDs, endpoints, conversation IDs, evaluation
IDs, or release IDs, and it does **not** reuse historical MAF deployment claims
as LangGraph evidence.

## Migration provenance

The imported Microsoft Agent Framework docs and delivery ledger were mined for
lessons learned, not for live proof. The approved LangGraph documentation set
keeps business behavior, stable contracts, privacy boundaries, Foundry hosting,
and release gates while replacing the workflow runtime assumptions.

## Adopted learnings from the reference ledger

### 1. Runtime DDL ownership

- Production schema DDL remains administrator-owned.
- Production startup sets `DB_SCHEMA_MANAGED_EXTERNALLY=true`.
- The runtime role must fail clearly if required schema objects are missing; it
  must not attempt schema creation or role management.

### 2. Portability, bootstrap, and reuse

- `bootstrap` creates the full public lane.
- `reuse` is non-mutating and must not create retained resources, connections,
  or RBAC assignments.
- Secret-free profiles select the target; generated names, IDs, and runtime
  values hydrate only the local environment.

### 3. Package feeds

- Python release images keep
  `PIP_INDEX_URL=https://packagefeedproxy.microsoft.io/pypi/simple`.
- Frontend and Playwright installs keep
  `https://packagefeedproxy.microsoft.io/npm/`.
- Package policy changes alone are not release evidence.

### 4. Immutable packaging and hosted source sync

- Hosted build context must be synchronized from canonical source before
  `azd package`.
- Generated hosted context is deployment output, not source of truth.
- Runtime artifacts deploy by immutable digest only.

### 5. PostgreSQL least privilege and readiness

- The runtime role keeps only connect, schema usage, required table DML, and
  required sequence usage.
- Readiness must verify TLS, canonical hostname, firewall posture, required
  tables, runtime connectivity, and denied DDL or role creation.
- Database recovery or availability incidents must be distinguished from graph
  logic regressions before changing code or permissions.

### 6. Foundry RBAC

- Foundry RBAC stays resource scoped and minimal.
- The hosted platform identity receives only the required account-scoped
  `Cognitive Services OpenAI User` runtime grant.
- Unexpected RBAC mutations are release stop conditions.

### 7. Telemetry and evaluation trace age

- Application Insights connection is required for release proof.
- Evaluation must consume only fresh hosted-E2E evidence after the configured
  trace-materialization age.
- Explicit completed evaluation status is required; stale or partial traces are
  not acceptable evidence.

### 8. Frontend proxy JSON failures

- Same-origin `/api` routes must return JSON or SSE on API paths.
- HTML fallbacks, content-type mismatches, and proxy-level failures are treated
  as topology defects, not workflow proof.
- Wrapper and proxy verification belongs in release validation.

### 9. Release timing and evidence integrity

- App-only release authority rejects durations above 15 minutes from package
  start to telemetry success.
- Timing data is valid only when packaging, deployment, smoke, hosted E2E,
  telemetry, and final evidence belong to one release window.
- Local timing artifacts help operators but do not replace reviewed evidence.

### 10. Privacy and release proof boundaries

- Browser-facing projections stay redacted.
- MCP, RAG, prompts, raw model output, checkpoint state, credentials, and
  secrets remain backend only.
- Repository configuration documents intent; it never proves a live endpoint.

## 2026-08-16 - LangGraph documentation translation

### Scope

- Rewrote README, agents guide, architecture, PRD, user flow, project
  structure, tech stack, HITL rules, schema and telemetry, deployment flow,
  engineering operating model, manual testing guidance, and summary pointer for
  the approved LangGraph direction.
- Replaced MAF-first workflow language with one shared LangGraph `StateGraph`,
  native `interrupt()` and `Command(resume=...)`, native PostgreSQL
  checkpointer guidance, and separate audit projections.
- Removed stale live-release claims and old deployment identifiers from
  documentation.

### Preserved contracts

- Business behavior and HITL thresholds
- Stable SSE and API event names
- Same-origin public browser topology
- Foundry container hosting
- Application Insights-only observability
- Privacy and redaction boundaries
- Release gating for readiness, immutable packaging, fresh E2E, evaluation, and
  evidence integrity

### Non-claims

- No backend, frontend, infra, or deployment files were changed in this
  documentation-only scope.
- No live deployment, smoke, E2E, evaluation, or telemetry proof is claimed by
  this entry.

## 2026-08-16 - Architecture remediation documentation follow-up

### Scope

- Clarified that only one unresolved interrupt may exist per thread and that
  new normal turns are rejected or deferred while approval is pending.
- Documented the native LangGraph checkpoint as workflow-state source of truth
  and the approval UUID table as an idempotent audit projection.
- Added startup and on-demand reconciliation guidance from graph state to audit
  rows.
- Clarified that projections must not duplicate authoritative action, order, or
  amount state.
- Added checkpoint-table privacy and retention guidance for resume-critical PII.
- Documented the app-lifetime singleton `AsyncPostgresSaver` pool and the rule
  that `checkpoint.created` and `hitl.request` are emitted during approval
  preparation rather than replayed from the resumed interrupt node.

### Non-claims

- This entry is documentation only.
- No runtime implementation or hosted evidence is claimed here.

## Pending implementation follow-through

The runtime cutover still must:

1. land the shared LangGraph runtime namespace and graph assembly,
2. preserve the stable browser API and SSE contracts,
3. wire `AsyncPostgresSaver` and separate audit projections correctly,
4. keep Foundry Responses 2.0 hosting thin and source-synchronized, and
5. regenerate fresh hosted smoke, E2E, telemetry, evaluation, and release
   evidence after the code migration completes.

## Stop conditions for the upcoming cutover

Stop the migration or release if it:

- broadens database permissions to avoid runtime DDL issues,
- introduces a second orchestration path,
- leaks resolved runtime secrets into hosted metadata or evidence,
- bypasses approved package feeds,
- drops same-origin proxy JSON or SSE behavior,
- requires LangSmith for release success, or
- relies on historical MAF evidence as LangGraph proof.

## 2026-08-16 - LangGraph implementation and Azure release completed

### Delivered

- Replaced the MAF workflow path with one shared LangGraph `StateGraph`.
- Added native PostgreSQL checkpointing, durable approval interrupts and
  resume, idempotency, audit projections, AG-UI, CopilotKit-safe projections,
  Docker packaging, Foundry Responses hosting, IaC, telemetry, and release
  evidence.
- Added strict hosted approval parsing through supported `x-client-*` headers;
  ordinary text remains a pending-only, whole-message fallback.
- Added administrator-owned application and LangGraph checkpoint schema
  bootstrap with least-privilege runtime grants.
- Made Foundry evaluation fail closed when a run has failed or errored items,
  no results, or no passing result.

### Local proof

- Backend: 126 tests passed.
- Deterministic evaluation: 11 of 11 cases passed.
- Playwright: 7 workflow scenarios and 3 selected-thread scenarios passed.
- Full local lifecycle: 141.40 seconds.

### Azure proof

- Target: `rg-langgraph-ora-foundry-public` in `eastus2`.
- Public frontend:
  `https://orderresoluta273f84f-frontend.icysmoke-032afb43.eastus2.azurecontainerapps.io`.
- Accepted release:
  `langgraph-order-resolution-20260816T200419Z-492664`.
- Release status: succeeded with deployment verification, hosted smoke,
  three-conversation hosted E2E, evaluation, telemetry, and secret-free final
  evidence.
- Foundry evaluation: 3 passed, 0 failed, 0 errored.
- Application Insights: 307 correlated rows for the three hosted E2E
  conversations.

### Accepted release timings

| Stage | Seconds |
| --- | ---: |
| Package build | 36.314 |
| Frontend deployment | 303.320 |
| Backend deployment | 455.975 |
| Hosted-agent activation | 205.512 |
| Deployment verification | 174.554 |
| Hosted smoke | 12.465 |
| Hosted E2E | 43.075 |
| Foundry evaluation | 193.332 |
| Telemetry verification | 9.002 |
| Final evidence | 0.169 |
| Package start to telemetry success | 888.544 |
| Complete release command | 1311.16 |

The release evidence is stored under the matching ignored
`.artifacts/releases/` directory and contains no credentials or resolved
database URLs.

## 2026-08-24 - Cross-lane Foundry session pool lifecycle learning

The private LangGraph lane exposed a PostgreSQL connection-lifecycle risk that
also applies to Foundry-hosted designs. A Foundry Responses conversation can
retain an idle hosted compute session, so an "application-lifetime" pool is
one pool per hosted session process, not one pool for the entire agent fleet.
LangGraph also owns both the synchronous audit repository pool and the
`AsyncPostgresSaver` pool.

The MAF private reference did not record this as an issue. It used only one
synchronous `ConnectionPool(min_size=1, max_size=10)`, created three fresh
hosted-E2E conversations, and retried transient hosted failures with 15-second
cooling intervals. The LangGraph private release combined hosted E2E with
several browser conversations and retained two pools per process, exposing the
runtime role's connection limit. This comparison identifies a latent
lifecycle difference rather than a regression in HITL behavior.

Adopt this cross-lane rule for future public releases: production pool sizing
must account for wrapper replicas, concurrent Foundry session processes, and
both LangGraph persistence pools. Hosted-session pools should permit a zero
idle floor, use a short idle lifetime, expose bounded maxima, and set distinct
PostgreSQL application names for operational attribution. Deployment
verification must reject drift from the lane's chosen limits. This entry
records the learning only; it does not replace fresh public-lane release
evidence.
