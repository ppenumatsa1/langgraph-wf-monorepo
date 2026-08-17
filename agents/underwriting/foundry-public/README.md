# LangGraph Underwriting Agent

## Goal

Build a verifiable underwriting workflow that preserves the existing product and browser contract while migrating the operator story, documentation, and skills to **LangGraph + Foundry Responses 2.0**.

The preserved operator contract includes:

- application-form submission,
- run history and selected-run refresh,
- happy, retry, crash, and resume flows,
- four-check fan-in visibility,
- checkpoint timeline and resume evidence,
- idempotency-skip evidence,
- same-origin `/api` and `/backend-health` proxy behavior,
- internal backend and browser privacy boundaries,
- stable REST, AG-UI, and CopilotKit behavior, and
- a strict safe selected-run allowlist.

The approved runtime direction is a **single shared LangGraph `StateGraph`** hosted locally through FastAPI and publicly through Azure AI Foundry Responses 2.0, with a native PostgreSQL checkpointer and Application Insights telemetry.

Historical Microsoft Agent Framework material is migration provenance only. It is not the architectural authority for this lane.

## Start here

1. **Product and business intent**
   - PRD: [docs/design/prd.md](docs/design/prd.md)
   - User flow: [docs/design/userflow.md](docs/design/userflow.md)
2. **Architecture and contracts**
   - Architecture: [docs/design/architecture.md](docs/design/architecture.md)
   - Architecture decisions: [docs/design/architecture-decisions.md](docs/design/architecture-decisions.md)
   - Schema, I/O, and telemetry: [docs/design/schema-io-telemetry.md](docs/design/schema-io-telemetry.md)
   - Customer questions and answers: [docs/design/customer-questions-answers.md](docs/design/customer-questions-answers.md)
3. **Delivery and release governance**
   - Engineering operating model: [docs/design/engineering-operating-model.md](docs/design/engineering-operating-model.md)
   - Deployment flow: [docs/design/deployment-flow.md](docs/design/deployment-flow.md)
   - Issues, changes, and adopted learnings ledger: [docs/design/issues-changes-fixes.md](docs/design/issues-changes-fixes.md)
4. **Repository operating guidance**
   - Agents guide: [agents.md](agents.md)
   - Project structure: [docs/design/projectstructure.md](docs/design/projectstructure.md)
   - Tech stack: [docs/design/techstack.md](docs/design/techstack.md)
   - Implementation phases: [docs/design/implementation-phases.md](docs/design/implementation-phases.md)
5. **Validation and operator guidance**
   - E2E rubric: [docs/design/e2e-rubric.md](docs/design/e2e-rubric.md)
   - Manual testing: [docs/manual-testing.md](docs/manual-testing.md)

## Documentation status

| Surface | Status | Meaning |
| --- | --- | --- |
| Underwriting business behavior | Preserved | Application intake, four-check fan-in, checkpoint resume, retry, idempotency, run history, and selected-run privacy contracts stay stable. |
| LangGraph runtime | Delivered | One shared graph now runs locally and through Foundry Responses 2.0 with native PostgreSQL checkpointing. |
| Live hosted evidence | Passed | Provenance-safe release `langgraph-underwriting-20260817T144804Z-final`, sourced from commit `ee5f1db`, passed smoke, E2E, Playwright, evaluation, telemetry, topology verification, and secret-free evidence aggregation. |

## Accepted release

| Measure | Result |
| --- | --- |
| Hosted agent | `underwriting-hosted` version `6`, active |
| Package through deployment | 509.283 seconds / 8.49 minutes |
| Package through telemetry | 1,142.407 seconds / 19.04 minutes |
| Hosted smoke | 204.208 seconds / 3.40 minutes |
| Hosted E2E and Playwright | 271.528 seconds / 4.53 minutes |
| Foundry evaluation | 1/1 passed; zero failed or errored |
| Application Insights | 76 correlated rows across all three E2E workflow runs; zero exceptions |
| PostgreSQL lifecycle | Per-invocation hosted pools close deterministically; runtime role limit 50 |

## Approved runtime shape

- One shared LangGraph `StateGraph` for `init_context`, parallel risk/credit/medical/driving checks, `fan_in_aggregator`, deterministic `final_decision`, and optional rationale generation.
- Native PostgreSQL checkpoint durability through LangGraph checkpointer support; checkpoint state is authoritative for resume.
- Separate PostgreSQL audit projections for workflow runs, workflow events, checkpoint summaries, underwriting results, idempotency records, and release evidence.
- Same-origin public browser flow: external frontend -> internal FastAPI wrapper -> Foundry Responses 2.0 -> shared PostgreSQL.
- AG-UI and CopilotKit remain additive, read-only, selected-run projections backed by durable data.
- Application Insights is the required observability backend. **LangSmith is not required.**

## Release and platform guardrails

- Production schema DDL remains administrator-owned.
  `DB_SCHEMA_MANAGED_EXTERNALLY=true` is required in production runtime startup.
- Routine releases are app-only, deploy immutable image digests, and must not accept `FOUNDRY_DEPLOY_MODE`.
- The browser never calls Foundry or PostgreSQL directly and never receives credentials.
- Hosted database values resolve only through the deterministic project `CustomKeys` connection placeholder.
- Release evidence must be fresh, release-window scoped, secret free, and recorded in [docs/design/issues-changes-fixes.md](docs/design/issues-changes-fixes.md).

## Required validation gates

Run these before calling a shared-surface change done:

```bash
make test
make quality
make test-e2e
```

For hosted packaging, deployment, or telemetry changes, also run:

```bash
make foundry-iac-build
make foundry-release-package
make foundry-release-build
make foundry-postgres-readiness
make foundry-model-preflight
make foundry-runtime-connection
make foundry-smoke
make foundry-eval
make foundry-verify
make foundry-evidence
```

When validating a deployed frontend, run hosted Playwright from `frontend/` with `PLAYWRIGHT_BASE_URL=<frontend-url> npm run test:e2e`.

## Documentation map

### Product and design

- PRD: [docs/design/prd.md](docs/design/prd.md)
- User flow: [docs/design/userflow.md](docs/design/userflow.md)
- Architecture: [docs/design/architecture.md](docs/design/architecture.md)
- Architecture decisions: [docs/design/architecture-decisions.md](docs/design/architecture-decisions.md)
- Schema and telemetry: [docs/design/schema-io-telemetry.md](docs/design/schema-io-telemetry.md)
- Customer Q&A: [docs/design/customer-questions-answers.md](docs/design/customer-questions-answers.md)

### Delivery and implementation

- Engineering operating model: [docs/design/engineering-operating-model.md](docs/design/engineering-operating-model.md)
- Deployment flow: [docs/design/deployment-flow.md](docs/design/deployment-flow.md)
- Project structure: [docs/design/projectstructure.md](docs/design/projectstructure.md)
- Tech stack: [docs/design/techstack.md](docs/design/techstack.md)
- Implementation phases: [docs/design/implementation-phases.md](docs/design/implementation-phases.md)

### Operations and evidence

- Manual testing: [docs/manual-testing.md](docs/manual-testing.md)
- Issues, changes, and adopted learnings ledger: [docs/design/issues-changes-fixes.md](docs/design/issues-changes-fixes.md)
- Summary pointer: [docs/issues-fixes.md](docs/issues-fixes.md)
