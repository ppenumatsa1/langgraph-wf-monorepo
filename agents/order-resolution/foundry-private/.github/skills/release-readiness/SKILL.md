---
name: release-readiness
description: Orchestrate focused repository skills for private-lane PR or release readiness across backend, docs, IaC, local validation, Azure validation, deployment, telemetry validation, and final design review.
---

# Release Readiness Skill

Use this skill when preparing a PR, release, or deployment handoff that may touch multiple repository surfaces.

## Principle

Compose focused skills instead of doing one broad review. Run only the skills relevant to the files changed, then run `design-review` as the final deterministic local gate.

## Skill routing

1. Backend/API/LangGraph changes -> run `backend-boundary-review`.
2. Documentation-impacting changes -> run `docs-sync`.
3. Local behavior changes -> run `local-validation`.
4. Azure/Foundry IaC, Docker, AZD, workflows, or smoke script changes -> run `iac-review`.
5. Azure readiness or deployed endpoint checks -> run `azure-validation`.
6. Already validated Azure deployment execution -> run `azure-deployment`.
7. Hosted App Insights proof after deployment -> run `azure-telemetry-validation`.
8. Workflow/runtime/HITL quality evidence -> run `order-resolution-evaluation`.
9. Final local gate -> run `design-review`.

## Recommended sequence

1. Inspect changed files and classify affected surfaces.
2. Route validation/deployment mode with:

```bash
scripts/skills/deployment-mode-router.sh
```

   - `validation_mode=quick` -> run `quick-validation`
   - `validation_mode=full` -> run `local-validation`
   - `deploy_mode=app_only` -> use `make foundry-private-release` only after
     private DNS, endpoint approval, identity/RBAC, and target readiness have
     already passed.
   - Every automatic route is `app_only`; router output never authorizes
     provisioning or public exposure.
   - Provisioning is exceptional: the existing provisioning target may run
     only from the private runner, in noninteractive preview mode, and must
     stop automatically on delete or replace changes.
3. Run independent focused reviews in parallel when safe.
4. Apply only material fixes from focused reviews.
5. Run `docs-sync` after code/IaC behavior is settled.
6. Run quick or full local validation based on routing output.
7. Run `azure-validation` when Azure artifacts or live endpoints are involved.
8. Run `azure-deployment` only when the plan is validated and the user wants deployment.
9. Run `azure-telemetry-validation` after hosted deployment when App Insights telemetry is in scope.
10. Run `design-review` last to confirm the deterministic local gate.

The app-only release reuses the approved private PostgreSQL, Foundry, ACR,
Application Insights, and BYO VNet resources. Its blocking path is selected
validation plus Bicep build, fresh package/readiness, backend/frontend/private
Foundry deployment, private ACR pull, Application Insights connection, smoke,
hosted E2E, report-only evaluation, and correlated telemetry. A quick
validation selection changes only local validation scope; it does not weaken
later hosted gates.

For frontend or hosted endpoint readiness, require Playwright evidence in both
local and hosted modes where applicable. Hosted proof must use the external
frontend URL, while internal wrapper and dependency connectivity is checked
from the private runner. It must fail if Workflow History shows `Unexpected
token`, `not valid JSON`, or `<!doctype`, which means the frontend received
HTML instead of API JSON.

## Guardrails

- Keep changes surgical and simplicity-first.
- Do not use this skill as permission for broad refactors.
- Do not deploy from this skill directly; invoke `azure-deployment` for live deployment execution.
- Never treat this skill as evidence that a live Azure deployment succeeded.
- Keep deployment automation noninteractive and fail closed on unexpected
  targets, destructive plans, missing private DNS, missing endpoint approval,
  missing RBAC, readiness failures, or secret-bearing artifacts.
- Deployment gates do not replace business HITL; risky order resolution must
  continue through LangGraph `interrupt()` and `Command(resume=...)`.
- Do not remove compatibility shims as part of release readiness unless shim removal is the explicit task.
- Report any skipped skill and why it was not applicable.

## Output

Report:

- skills run
- material findings fixed
- commands run
- blockers
- final readiness status
