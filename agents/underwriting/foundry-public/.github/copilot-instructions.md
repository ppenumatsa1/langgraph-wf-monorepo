# Copilot Instructions

This lane documents and validates the approved **LangGraph underwriting workflow** target while preserving the existing underwriting product and browser contract.

## Runtime contract

- Keep one shared LangGraph `StateGraph` for local FastAPI validation and Azure AI Foundry Responses 2.0 hosting.
- Keep the deterministic underwriting policy inside the graph: risk, credit, medical, and driving checks fan out, `fan_in_aggregator` merges results, and `final_decision` remains authoritative before any rationale is attached.
- Treat the native PostgreSQL LangGraph checkpointer as the source of truth for resume state.
  Separate application tables provide run history, event timeline, checkpoint summaries, underwriting results, idempotency evidence, and release evidence.
- Preserve `workflow_run_id`-scoped crash and resume behavior.
  Replay and resume must stay idempotent and observable.
- Preserve the stable browser contract:
  - application form,
  - run history,
  - durable run/state/events/checkpoints APIs,
  - AG-UI stream updates, and
  - CopilotKit selected-run explanation.
- Preserve the strict selected-run privacy allowlist.
  Never expose applicant details, health disclosures, income, credit scores, prompts, raw model output, checkpoint payloads, credentials, or secrets.
- PostgreSQL DDL is administrator-owned.
  Hosted runtimes set `DB_SCHEMA_MANAGED_EXTERNALLY=true` and must not require broad `CREATE` or schema ownership.

## Stable application boundaries

- HTTP, AG-UI, and CopilotKit entrypoints: `backend/app/api/v1/routes/*`
- API schemas: `backend/app/api/v1/schemas/*`
- Domain, service, deterministic decision, and safe selected-run projection logic: `backend/app/modules/underwriting/*`
- Configuration, telemetry, and app composition: `backend/app/core/*`
- Persistence, Foundry clients, and runtime adapters: `backend/app/infrastructure/*`
- LangGraph target namespace: `backend/app/langgraph/*`
- Hosted entrypoint: `backend/foundry/main.py`

Legacy `backend/app/maf/*` directories are migration provenance only. Do not preserve them as the architectural end state and do not create a second workflow path beside the shared LangGraph runtime.

## Hosting and telemetry

- Public topology: external frontend Container App -> same-origin `/api` proxy -> internal FastAPI wrapper -> Foundry Responses 2.0 hosted agent -> shared PostgreSQL.
- The browser must never call Foundry or PostgreSQL directly and must never receive credentials.
- Hosted database values use only the deterministic project `CustomKeys` connection placeholder; never persist the resolved URL in metadata or evidence.
- Application Insights is the required observability backend. LangSmith is not required.
- Preserve request, workflow, Foundry, model, retry, checkpoint, idempotency, and final-decision correlation.
- Health and long-lived stream noise should stay filtered from request telemetry so workflow signal remains visible.

## Delivery

- Routine releases are app-only and deploy immutable image digests.
- Preserve approved Python and npm package feeds.
- Do not copy historical MAF deployment identifiers or success claims as LangGraph evidence.

Required local gates:

```bash
make test
make quality
make test-e2e
```

Required deployment and hosted gates when applicable:

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

Read the lane-local `langgraph-docs` and `langgraph-foundry-py` skills before changing graph code. Read `microsoft-foundry` before changing hosted-agent deployment, evaluation, or telemetry behavior.
