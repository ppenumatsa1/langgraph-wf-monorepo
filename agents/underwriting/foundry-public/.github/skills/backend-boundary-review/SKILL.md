---
name: backend-boundary-review
description: Review underwriting backend changes for canonical ownership, no-shim rules, safe hosted relay boundaries, and contract stability.
---

# Backend Boundary Review Skill

Use this skill when reviewing backend changes for repository boundary compliance.

## Canonical ownership

- `backend/app/api/v1/routes/*` owns HTTP, AG-UI, and CopilotKit route entrypoints only.
- `backend/app/api/v1/schemas/*` owns API request and response contracts.
- `backend/app/modules/underwriting/*` owns service/domain seams, hosted relay envelopes, safe selected-run assistant context, and deterministic decision policy.
- `backend/app/core/*` owns config, telemetry, and application composition.
- `backend/app/infrastructure/*` owns PostgreSQL, repository adapters, Foundry clients, and runtime persistence.
- `backend/app/langgraph/*` is the target workflow runtime namespace for graph composition, nodes, prompts, and checkpoints.
- `backend/foundry/main.py` owns the hosted Responses execution entrypoint.

Legacy `backend/app/maf/*` code is migration provenance only and must not grow into a second workflow authority.

## Review guardrails

- Reject new canonical code that introduces alternate orchestration layers or compatibility shims.
- Keep the internal backend wrapper as a relay and projection layer; it must not construct a second hosted workflow path.
- Keep AG-UI additive to durable read models and keep CopilotKit on its allowlisted metadata boundary.
- Preserve fan-out/fan-in, checkpoint resume, retry, and idempotency semantics unless intentionally changed.
- Keep deterministic decision policy authoritative; rationale generation may explain the outcome but must not override it.
- Require frontend, Playwright, and documentation updates for intentional API, read-model, AG-UI, CopilotKit, or event contract changes.

## Required checks

1. Inspect touched backend files for misplaced HTTP, schema, domain, core, infrastructure, or LangGraph responsibilities.
2. Block newly introduced shims, duplicate route surfaces, or alternate workflow entrypoints.
3. For workflow, fan-in, retry, resume, or idempotency changes, verify matching coverage in backend tests such as `test_fan_in.py`, `test_resume.py`, `test_idempotency.py`, `test_run_history.py`, and `test_observability.py`.
4. For AG-UI or CopilotKit changes, verify matching updates in frontend E2E coverage and design docs.
5. For hosted relay or telemetry changes, verify trace-evaluation and hosted-correlation coverage remain aligned.

## Pass/fail behavior

- Pass when changes preserve canonical boundaries and required test/doc updates are present.
- Fail when code crosses boundaries, widens the safe assistant surface, introduces shims, or changes contracts without matching tests and docs.

