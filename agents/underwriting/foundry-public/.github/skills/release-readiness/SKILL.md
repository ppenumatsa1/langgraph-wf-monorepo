---
name: release-readiness
description: Orchestrate underwriting repository skills for PR or release readiness across boundaries, docs, local validation, Azure readiness, deployment, telemetry, and evaluation.
---

# Release Readiness Skill

Use this skill when preparing a PR, release, or deployment handoff that may touch multiple repository surfaces.

## Principle

Compose focused skills instead of doing one broad review. Run only the skills relevant to the files changed, then finish with `design-review`.

## Skill routing

1. Backend, workflow, persistence, or hosted-relay changes -> `backend-boundary-review`
2. AG-UI, CopilotKit, or frontend TypeScript changes -> `ag-ui-streaming-fastapi-py`, `ag-ui-react-integration-ts`, or `e2e-rubric` as applicable
3. Documentation-impacting changes -> `docs-sync`
4. Low-risk app-only changes -> `quick-validation`
5. Shared local behavior changes -> `local-validation`
6. Azure, Foundry, Docker, AZD, PostgreSQL, or release script changes -> `iac-review`
7. Azure readiness or deployed endpoint checks -> `azure-validation`
8. Validated live deployment execution -> `azure-deployment`
9. Hosted quality evidence -> `underwriting-evaluation`
10. Post-deploy trace proof -> `azure-telemetry-validation`
11. Final focused gate -> `design-review`

## Recommended sequence

1. Inspect changed files and classify the affected surfaces.
2. Choose quick validation only for low-risk app-only changes with unchanged workflow, persistence, AG-UI, CopilotKit, and hosted contracts.
3. Run boundary, frontend, and docs skills first so fixes stay surgical.
4. Run `local-validation` or `quick-validation` based on the actual change surface.
5. Add `iac-review` and `azure-validation` when the public lane, release scripts, or hosted runtime are involved.
6. Run `azure-deployment` only when the plan is validated and deployment is explicitly in scope.
7. For a full release, use the checked-in concurrency model: shared readiness once, independent component deployment fan-out, smoke, parallel E2E/eval, then telemetry as soon as E2E evidence exists.
8. Run `underwriting-evaluation` and `azure-telemetry-validation` for hosted runtime, telemetry, or public release work.
9. Run `design-review` last.

## Guardrails

- Keep changes surgical and simplicity-first.
- Do not use this skill as permission for broad refactors.
- Do not deploy from this skill unless deployment is explicitly part of the task and validation has already passed.
- Preserve all release gates. Optimize wall-clock time only through safe parallel work; never weaken the evidence contract to meet a timing target.
- Report every skipped skill and why it was not applicable.

## Output

Report:

- skills run
- material findings fixed
- commands run
- blockers
- final readiness status
