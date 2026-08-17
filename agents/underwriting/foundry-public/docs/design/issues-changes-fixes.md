# LangGraph Issues, Changes, and Adopted Learnings

## Evidence rule

This ledger records:

- adopted operational learnings from the historical underwriting reference lane,
- the completed LangGraph implementation and hosted lifecycle,
- root-cause analysis and remediations, and
- current release evidence.

It does **not** copy historical release IDs, evaluation IDs, revision names, smoke run IDs, or success claims as LangGraph evidence.

## Migration provenance

The imported underwriting MAF docs, instructions, and release ledger were mined for lessons learned, not for live proof. The approved documentation set keeps business behavior, browser contracts, privacy boundaries, Foundry hosting, and release gates while replacing the runtime assumptions with LangGraph, native PostgreSQL checkpointing, Foundry Responses 2.0, and Application Insights.

## Adopted learnings from the reference lane

### 1. Runtime DDL ownership

- Production schema DDL remains administrator-owned.
- Production startup sets `DB_SCHEMA_MANAGED_EXTERNALLY=true`.
- The runtime role must fail clearly if required schema objects are missing; it must not attempt schema creation or privilege escalation.

### 2. Portability, bootstrap, and reuse

- `bootstrap` creates the full public lane.
- `reuse` is non-mutating and must not create retained resources, connections, or RBAC assignments.
- Secret-free profiles select the target; generated runtime values hydrate only the local environment.

### 3. Package feeds and immutable packaging

- Python release images keep the approved Microsoft package feed.
- Frontend and Playwright installs keep the approved Microsoft npm feed.
- Hosted build context must be synchronized from canonical source before packaging.
- Runtime artifacts deploy by immutable digest only.

### 4. PostgreSQL least privilege and readiness

- The runtime role keeps only connect, schema usage, required table DML, and required sequence usage.
- Readiness must verify TLS, canonical hostname, firewall posture, required tables, runtime connectivity, and denied DDL or role creation.
- Database incidents must be distinguished from graph regressions before changing code or permissions.

### 5. Same-origin proxy correctness

- Same-origin `/api` routes must return JSON or SSE.
- HTML fallbacks, content-type mismatches, and proxy-level failures are topology defects, not workflow proof.
- External frontend plus internal backend topology must remain release-verified.

### 6. Telemetry and evaluation integrity

- Application Insights connection is required for release proof.
- Evaluation must consume only fresh hosted evidence and remain secret free.
- Explicit completed evaluation status is required; stale or partial traces are not acceptable evidence.

### 7. Privacy boundaries

- Browser-facing projections stay redacted and allowlisted.
- Checkpoint payloads, prompts, raw model output, credentials, and secrets remain backend only.
- Repository configuration documents intent; it never proves a live endpoint.

## 2026-08-16 - UI, documentation, and skill migration

### Scope

- Rewrote lane README, agents guidance, Copilot instructions, design docs, manual testing guide, and issues summary around the approved LangGraph runtime direction.
- Replaced lane-owned MAF workflow skills with LangGraph documentation, LangGraph + Foundry runtime, and underwriting evaluation skills.
- Removed duplicate generic Agent Framework, Foundry evaluation, and TypeScript
  setup/update skills; added a complete reviewed provenance lock and automated
  skill inventory, frontmatter, stale-identifier, and local-link validation.
- Updated frontend copy and Playwright rubric wording to describe LangGraph runs, durable checkpoints, and the strict selected-run allowlist without changing the browser contract.
- Replaced the historical delivery ledger with this fresh LangGraph migration ledger.

### Preserved contracts

- application form and scenario entry
- run history and selected-run refresh
- happy, retry, crash, and resume flows
- four-check fan-in display
- checkpoint timeline and resume affordance
- idempotency-skip evidence
- same-origin frontend proxy and internal backend
- stable REST, AG-UI, and CopilotKit behavior
- strict safe selected-run privacy allowlist

### Validation

- Frontend dependencies: passed via `cd frontend && npm install`.
- Backend validation prerequisites: passed via `make install` to create `.venv` for local E2E startup.
- Frontend lint: passed via `cd frontend && npm run lint`.
- Frontend build: passed via `cd frontend && npm run build`.
- Playwright E2E: blocked on existing backend schema drift. Local run reached backend startup and AG-UI dispatch, but the workflow failed with `psycopg.errors.UndefinedColumn: column "started_at" of relation "workflow_runs" does not exist`, leaving the happy-path run stuck at `RUNNING`.
- Additional docs or skill validation: completed by spot-checking the rewritten README, agents guide, skill docs, frontend copy, and the fresh ledger for LangGraph terminology and selected-run privacy alignment.

### Non-claims

- No backend, infra, deployment, Makefile, or root files were changed in this migration scope.
- No live deployment, smoke, evaluation, or telemetry proof is claimed by this entry.

## 2026-08-17 - LangGraph runtime and hosted release completed

### Delivered

- Replaced the underwriting MAF runtime with one shared LangGraph `StateGraph`.
- Preserved deterministic risk, credit, medical, and driving fan-out/fan-in,
  final decision authority, retry, crash-resume, idempotency, REST, AG-UI,
  CopilotKit, and selected-run privacy contracts.
- Added native PostgreSQL LangGraph checkpointing plus separate durable audit
  projections.
- Deployed the external frontend, internal FastAPI wrapper, and Foundry
  Responses 2.0 hosted agent with immutable image digests.
- Added mandatory Docker-context exclusions and ACR builds with verified reuse
  of unchanged image digests.

### Issues, RCA, and fixes

| Issue | Root cause | Fix |
| --- | --- | --- |
| Runtime grants failed | Native LangGraph checkpoint tables were absent | Administrator bootstrap now creates checkpointer tables before least-privilege grants. |
| Images missed `psycopg_pool` | Docker installed a stale lane-root manifest | Docker contexts install the backend manifest and fail builds on missing runtime imports. |
| Hosted startup failed | Hosted source was under `/app/backend` but `PYTHONPATH` used `/app` | Hosted image uses `/app/backend` and validates `foundry.main` during build. |
| Frontend proxy returned HTML | Backend ingress retained target port 80 while FastAPI listens on 8000 | Backend deployment converges target port 8000 and verifies same-origin JSON health. |
| Hosted workflows exhausted PostgreSQL connections | Loop-cached services retained checkpointer pools and the runtime role limit was 20 | Hosted services are created and closed per invocation, startup is inside cleanup scope, pools are bounded, and the justified role limit is 50. |
| Final evidence rejected a valid lifecycle | One 15-minute ceiling incorrectly covered deployment plus serial smoke/E2E/telemetry | Authority now enforces a 15-minute package-to-deployment budget and a separate 30-minute package-to-telemetry lifecycle budget. |
| Successful deployment lacked exact source provenance | The prior release was built from an uncommitted worktree while its record referenced the previous `HEAD` | Releases now require a clean lane, bind each image to a deterministic source fingerprint, and reject reused digests without the matching ACR source tag. |
| First provenance-safe build missed the deployment SLO by 2.850 seconds | Fresh ACR builds plus hosted activation and Container Apps deployment took 902.850 seconds / 15.05 minutes | The source-bound immutable images were retained, verified, and reused for the unchanged-source retry; the accepted release completed package-to-deployment in 509.283 seconds / 8.49 minutes. |
| Evidence files could be registered without proving gate semantics | Aggregation checked freshness and secret safety but not each gate's success fields | Aggregation now validates canonical target, topology, readiness, E2E, smoke, evaluation, and telemetry success before registering release gates. |

### Accepted release evidence

- Release: `langgraph-underwriting-20260817T144804Z-final`
- Source commit: `ee5f1dbf78be0d9428de1971f5b37050db604836`
- Hosted agent: `underwriting-hosted` version `6`, active
- Package to deployment: `509.283s` / `8.49m`
- Package to telemetry: `1,142.407s` / `19.04m`
- Hosted smoke: `204.208s` / `3.40m`
- Hosted E2E plus deployed Playwright: `271.528s` / `4.53m`
- Foundry evaluation: `1/1` passed, zero failed or errored
- Application Insights: `76` correlated rows for all three hosted E2E runs,
  zero exception rows
- PostgreSQL: readiness, schema/index parity, TLS, external schema management,
  dual authentication, restricted runtime credential, and bounded pool
  configuration passed
- Topology verification: external frontend, internal backend, same-origin
  health/API, direct backend not publicly reachable
- Evidence: release-local, secret-free, hashed, and finalized successfully

## Ongoing stop conditions

Stop the migration or release if it:

- broadens database permissions to avoid runtime DDL issues,
- introduces a second orchestration path,
- leaks resolved runtime secrets into hosted metadata or evidence,
- drops same-origin JSON or SSE behavior,
- widens the selected-run assistant allowlist,
- requires LangSmith for release success, or
- relies on historical MAF evidence as LangGraph proof.
