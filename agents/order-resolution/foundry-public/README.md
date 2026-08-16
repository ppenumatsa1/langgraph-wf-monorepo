# LangGraph Order Resolution Agent

## Goal

Build a verifiable customer-support workflow that:

- auto-resolves low-risk cases,
- pauses for human approval on risky cases, and
- preserves timeline and audit history end to end.

The approved runtime direction is a **single shared LangGraph StateGraph**
hosted locally through FastAPI and publicly through Azure AI Foundry Responses
2.0 container hosting.

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
- Same-origin public browser flow: external frontend -> internal FastAPI
  wrapper -> Foundry Responses 2.0 -> shared PostgreSQL.
- Application Insights is the only required observability backend.
  **LangSmith is not required.**
- AG-UI and CopilotKit remain optional, redacted, read-only selected-thread
  projections.

Historical Microsoft Agent Framework reference material is migration provenance
only. It informs the cutover plan but is not the architecture authority for
this lane.

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
| Business behavior and contracts | Approved | Low-risk completion, HITL gating, privacy, and SSE/API contracts stay stable. |
| LangGraph runtime design | Approved | Docs now describe the shared `StateGraph`, native interrupts, and `AsyncPostgresSaver` target shape. |
| Live deployment evidence | Regenerate after cutover | Historical MAF-era release evidence is not reused as LangGraph evidence. |

## Release and platform guardrails

- Production schema DDL remains administrator-owned.
  `DB_SCHEMA_MANAGED_EXTERNALLY=true` is required in production runtime
  startup.
- Bootstrap creates the complete public lane; reuse is non-mutating and must
  not create resources, RBAC assignments, or retained-state changes.
- Runtime PostgreSQL access stays least-privilege: connect, schema usage,
  required DML, and required sequence usage only.
- Native checkpoint tables may contain workflow PII needed for resume. Their
  retention, access, and export handling must stay more restrictive than
  redacted browser projections and general audit summaries.
- Hosted package generation must sync from the canonical backend source before
  `azd package`, and every deployed image must be pinned by immutable digest.
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
make eval-foundry
make test-e2e
./scripts/skills/design-review-skill.sh
```

For deployment and hosted packaging changes, also run:

```bash
make test-deployment-profile
make test-scripts
make foundry-iac-build
make foundry-package
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
