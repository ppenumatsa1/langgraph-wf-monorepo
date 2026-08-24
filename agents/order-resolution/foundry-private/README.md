# LangGraph Order Resolution - Private Lane

## Goal

Build a verifiable customer-support workflow that:

- auto-resolves low-risk cases,
- pauses for human approval on risky cases, and
- preserves timeline and audit history end to end.

The approved runtime direction is a **single shared LangGraph StateGraph**
hosted locally through FastAPI and deployed through an isolated BYO VNet. The
private Foundry runtime is reached only by the internal wrapper; it is not a
browser-facing public endpoint.

## Approved runtime shape

- One shared LangGraph `StateGraph` for triage, policy retrieval, resolution,
  and explanation.
- Native LangGraph `interrupt()` for human review and `Command(resume=...)`
  for approval or rejection.
- Native PostgreSQL checkpointer via `AsyncPostgresSaver` for thread-scoped
  graph state, plus separate PostgreSQL audit projections for runs, events,
  approvals, transcripts, and release evidence.
- One unresolved interrupt per thread. While approval is pending, new normal
  user turns are rejected or explicitly deferred until that interrupt is
  resolved.
- Native LangGraph checkpoints are the workflow-state source of truth.
  Approval UUID records are an idempotent audit projection, not a second copy
  of authoritative workflow state.
- The `AsyncPostgresSaver` pool is an app-lifetime singleton shared by graph
  execution rather than created per request.
- Stable browser API and SSE event names:
  `workflow.stage`, `tool.call`, `checkpoint.created`, `hitl.request`,
  `hitl.response`, and `workflow.output`.
- Same-origin browser flow: external frontend -> internal FastAPI wrapper ->
  private Foundry -> private PostgreSQL.
- Application Insights is the only required observability backend.
  **LangSmith is not required.**
- AG-UI and CopilotKit remain optional, redacted, read-only selected-thread
  projections.

## Private network contract

The lane uses a primary BYO VNet with address space `10.74.0.0/16` and a
dedicated Foundry network-injection VNet with address space `10.76.0.0/16`.
The VNet split prevents a failed Foundry service-link operation from
contaminating the application, endpoint, or runner subnets.

| Subnet | CIDR | Responsibility |
| --- | --- | --- |
| Foundry integration | `10.76.0.0/24` | Private Foundry integration and delegated network requirements |
| Foundry dependency endpoints | `10.76.1.0/24` | Lane-owned ACR, Storage, Cosmos DB, and Search endpoints for hosted compute |
| Container Apps | `10.74.2.0/23` | External frontend and internal FastAPI wrapper |
| Private endpoints | `10.74.4.0/24` | Private endpoints for Foundry, PostgreSQL, and ACR |
| Runner | `10.74.5.0/27` | Private, noninteractive Azure automation runner |

Only the frontend has external ingress. The wrapper has internal ingress, and
Foundry, PostgreSQL, ACR, and the runner remain private. Private DNS is part of
the connectivity contract, not an optional post-deployment enhancement.

## Design status

This workstream documents and governs the private lane. It does not claim that
Azure resources have been provisioned or that a private endpoint, DNS,
Application Insights, smoke, E2E, evaluation, or release check has succeeded.
Use the design ledger for the explicit non-claims and implementation boundary.

## Start here

1. **Product and business intent**
   - PRD: [docs/design/prd.md](docs/design/prd.md)
   - User flow: [docs/design/userflow.md](docs/design/userflow.md)
2. **Architecture and contracts**
   - Architecture: [docs/design/architecture.md](docs/design/architecture.md)
   - HITL decision rules: [docs/design/hitl-approval-conditions.md](docs/design/hitl-approval-conditions.md)
   - API, event, and telemetry schema: [docs/design/schema-io-telemetry.md](docs/design/schema-io-telemetry.md)
3. **Delivery and release governance**
   - Engineering operating model: [docs/design/engineering-operating-model.md](docs/design/engineering-operating-model.md)
   - Deployment flow: [docs/design/deployment-flow.md](docs/design/deployment-flow.md)
   - Issues, changes, and adopted learnings ledger: [docs/design/issues-changes-fixes.md](docs/design/issues-changes-fixes.md)
4. **Repository operating guidance**
   - Agents guide: [agents.md](agents.md)
   - Project structure: [docs/design/projectstructure.md](docs/design/projectstructure.md)
   - Tech stack: [docs/design/techstack.md](docs/design/techstack.md)
   - Manual testing: [docs/manual-testing.md](docs/manual-testing.md)

## Documentation status

| Surface | Status | Meaning |
| --- | --- | --- |
| Business behavior and contracts | Approved target | Low-risk completion, HITL gating, privacy, and SSE/API contracts remain stable. |
| LangGraph runtime design | Approved target | Docs describe the shared `StateGraph`, native interrupts, and `AsyncPostgresSaver` target shape. |
| Private network design | Documented target | BYO VNet, subnet reservations, private services, private runner, and fail-closed automation are specified. |
| Live deployment evidence | Not claimed | This documentation workstream contains no live Azure success evidence. |

## Release and platform guardrails

- Production schema DDL remains administrator-owned.
  `DB_SCHEMA_MANAGED_EXTERNALLY=true` is required in production runtime
  startup.
- Bootstrap creates the complete private lane; reuse is non-mutating and must
  not create resources, RBAC assignments, or retained-state changes.
- Runtime PostgreSQL access stays least-privilege: connect, schema usage,
  required DML, and required sequence usage only.
- Native checkpoint tables may contain workflow PII needed for resume. Their
  retention, access, and export handling must stay more restrictive than
  redacted browser projections and general audit summaries.
- Hosted package generation must sync from the canonical backend source before
  `azd package`, and every deployed image must be pinned by immutable digest.
- Authenticated deployment runs only from the private runner and fails closed
  on target, DNS, RBAC, preview, readiness, or evidence violations.
- Python and npm package acquisition must stay on the approved Microsoft feeds:
  `https://packagefeedproxy.microsoft.io/pypi/simple` and
  `https://packagefeedproxy.microsoft.io/npm/`.
- Release evidence must be fresh, release-window scoped, and secret free.
  Repository configuration is never deployment proof.

## Required validation gates

Run these before calling a behavior, runtime, or hosted release change done:

```bash
make test
make eval-backend
make test-e2e
./scripts/skills/design-review-skill.sh
```

For deployment and hosted packaging changes, also run:

```bash
make test-deployment-profile
make test-scripts
make foundry-private-gates
make foundry-private-iac-build
make foundry-private-package
make foundry-private-verify
make foundry-private-eval
make foundry-private-telemetry
```

## Documentation map

### Product and design

- PRD: [docs/design/prd.md](docs/design/prd.md)
- User flow: [docs/design/userflow.md](docs/design/userflow.md)
- Architecture: [docs/design/architecture.md](docs/design/architecture.md)
- HITL rules: [docs/design/hitl-approval-conditions.md](docs/design/hitl-approval-conditions.md)
- Schema and telemetry: [docs/design/schema-io-telemetry.md](docs/design/schema-io-telemetry.md)

### Delivery and implementation

- Engineering operating model: [docs/design/engineering-operating-model.md](docs/design/engineering-operating-model.md)
- Deployment flow: [docs/design/deployment-flow.md](docs/design/deployment-flow.md)
- Project structure: [docs/design/projectstructure.md](docs/design/projectstructure.md)
- Tech stack: [docs/design/techstack.md](docs/design/techstack.md)

### Operations and evidence

- Manual testing: [docs/manual-testing.md](docs/manual-testing.md)
- Issues, changes, and adopted learnings ledger: [docs/design/issues-changes-fixes.md](docs/design/issues-changes-fixes.md)
- Short pointer: [docs/issues-fixes.md](docs/issues-fixes.md)
