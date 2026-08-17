# Agents Guide

This file defines the approved documentation and operator-contract baseline for coding agents working in this lane.

## Project context

- Backend target: internal-ingress FastAPI wrapper plus one shared LangGraph `StateGraph` underwriting workflow.
  Legacy `backend/app/maf/*` directories may still exist during migration, but they are provenance only and must not become a second workflow path.
- Hosted runtime target: `backend/foundry/main.py` stays a thin Foundry Responses 2.0 host around the shared underwriting service.
- Public browser delivery: external React + Vite frontend -> same-origin `/api` proxy -> internal FastAPI wrapper -> Foundry Responses 2.0 -> shared PostgreSQL.
- Business flow: `init_context` fans out to risk, credit, medical, and driving checks in one graph run; `fan_in_aggregator` merges results; `final_decision` stays deterministic before any rationale is attached.
- Durability target: a native PostgreSQL LangGraph checkpointer owns authoritative resume state; separate projections own run history, events, checkpoint summaries, final decisions, idempotency evidence, and release evidence.
- Telemetry target: preserve request correlation, Foundry invocation spans, fan-out/fan-in, retry/backoff, checkpoint save/load, idempotency skip, and final decision traces in Application Insights.
- Browser privacy: CopilotKit may expose only selected run id, normalized status, safe event and executor metadata, checkpoint summary, and categorical final decision.

## Agent change policy

1. Keep changes focused on the requested surface.
2. Use one LangGraph underwriting workflow path. Do not create a parallel orchestrator, assistant-only path, or hosted-only workflow.
3. Preserve deterministic four-check fan-out/fan-in, checkpoint resume, retry, and idempotency semantics unless the task explicitly changes them.
4. Preserve the stable browser contract:
   - application form,
   - run history,
   - durable run/state/events/checkpoints endpoints,
   - AG-UI stream updates consumed by the frontend, and
   - CopilotKit selected-run explanation.
5. Keep AG-UI additive to durable projections; do not move operator state to stream-only behavior.
6. Preserve the CopilotKit allowlist boundary. Never expose applicant details, health disclosures, income, credit scores, prompts, raw model output, checkpoint payloads, credentials, or secrets.
7. If API, read-model, AG-UI, CopilotKit, or event contracts change intentionally, update frontend, Playwright, and documentation in the same change set.
8. Never remove coverage for:
   - happy-path completion
   - retry then completion
   - crash and resume from checkpoint
   - fan-in visibility for risk, credit, medical, and driving
   - checkpoint visibility
   - idempotency-skip visibility
   - observability fields in emitted events
   - same-origin frontend/internal-backend topology
   - hosted smoke/evaluation evidence
9. Production runtime schema stays administrator-owned.
   `DB_SCHEMA_MANAGED_EXTERNALLY=true` may validate schema parity but must not create or alter tables or indexes.
10. Routine release mode is always `app_only`. Never accept `FOUNDRY_DEPLOY_MODE` or reintroduce a public-ingress toggle for the backend.
11. Hosted agent metadata must contain only the deterministic `CustomKeys` connection placeholder for runtime database values; the resolved URL belongs only in runtime secret delivery.

## Required verification before completing work

Run the smallest existing applicable gate set and report what happened:

- `make test`
- `make quality` for frontend or shared-surface changes
- `make test-e2e` for UI, API, AG-UI, CopilotKit, or durable-history changes
- `make foundry-iac-build`, `make foundry-release-package`, `make foundry-release-build`, `make foundry-postgres-readiness`, `make foundry-model-preflight`, and `make foundry-runtime-connection` for hosted release or IaC changes
- `make foundry-smoke` and `make foundry-eval` for hosted runtime, deployment, or telemetry changes
- `make foundry-verify` and `make foundry-evidence` after an authenticated release

When validating a deployed frontend, run hosted Playwright from `frontend/` with `PLAYWRIGHT_BASE_URL=<frontend-url> npm run test:e2e`.
If a gate cannot run, report the exact blocker and rerun command.

## Repository skills

Use focused skills instead of one broad review pass:

- `design-review`
- `docs-sync`
- `backend-boundary-review`
- `local-validation`
- `quick-validation`
- `iac-review`
- `azure-validation`
- `azure-deployment`
- `azure-telemetry-validation`
- `underwriting-evaluation`
- `release-readiness`

## Stack implementation skills

Load only the relevant implementation skill for the task:

- `langgraph-docs`
- `langgraph-foundry-py`
- `microsoft-foundry`
- `azure-ai-projects-py`
- `azure-identity-py`
- `azure-monitor-opentelemetry-py`
- `fastapi-router-py`
- `pydantic-models-py`
- `postgres-psycopg-py`
- `ag-ui-streaming-fastapi-py`
- `ag-ui-react-integration-ts`
- `typescript-setup`
- `typescript-update`
- `e2e-rubric`

## E2E and hosted release baseline

Use `frontend/tests/e2e/rubric.ts` and `frontend/tests/e2e/underwriting.spec.ts` as the operator-facing baseline.

Required scenarios:

- happy path
- retry path
- crash at `medical_check`
- resume from checkpoint
- fan-in state contains risk, credit, medical, and driving results
- checkpoint list populated
- idempotency-skip event visible after resume/replay
- event payload contains observability fields
- selected-run assistant stays on the safe allowlist

Release-only criterion: public hosted smoke and Foundry evaluation must show correlation between the public request, hosted workflow trace, and safe hosted conversation evidence.

## Documentation update contract

When architecture, workflow contracts, release gates, or operator-facing behavior change, update the smallest relevant set of:

- `.github/copilot-instructions.md`
- `agents.md`
- `README.md`
- `docs/design/architecture.md`
- `docs/design/deployment-flow.md`
- `docs/design/schema-io-telemetry.md`
- `docs/design/userflow.md`
- `docs/design/e2e-rubric.md`
- `docs/design/issues-changes-fixes.md`
- `docs/manual-testing.md`
