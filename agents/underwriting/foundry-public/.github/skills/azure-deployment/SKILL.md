---
name: azure-deployment
description: Execute already validated underwriting Azure deployments and verify the live public lane.
---

# Azure Deployment Skill

Use this skill only after Azure validation passes.

## Hard gates

- Require authenticated Azure and `azd` context via `make foundry-bootstrap`.
- Run `make foundry-postgres-readiness` before deploying hosted runtime changes.
- Do not run the destructive PostgreSQL rebuild path unless the user explicitly requested that exact action with the required confirmation token.

## Deployment sequence

Use only the existing repository commands that match the changed surface:

```bash
make foundry-provision
make foundry-postgres-schema
make foundry-postgres-credentials
make foundry-postgres-readiness
make foundry-deploy
make foundry-release-deploy
make foundry-backend-deploy
make foundry-frontend-deploy
```

Guidance:

- Infra/auth/firewall changes -> include `make foundry-provision` and the PostgreSQL credential/schema steps.
- Hosted agent/runtime changes -> `make foundry-deploy`.
- Internal backend adapter changes -> `make foundry-backend-deploy`.
- External proxy frontend changes -> `make foundry-frontend-deploy`.
- Use `make foundry-release-deploy` for a complete release deployment. It runs
  PostgreSQL readiness once, packages all services, deploys the hosted agent
  and persists its active metadata, then builds/deploys the internal backend
  and external frontend concurrently.
- Backend and frontend remain parallel only after hosted metadata is durable.
  The frontend resolves the existing stable backend FQDN and does not require
  the backend image rollout to finish first.
- Provision only for actual IaC changes. Application, Docker, script, and
  telemetry changes reuse existing infrastructure after the validated preview.
- For a legacy environment whose backend still has external ingress, run the
  fail-closed `make foundry-backend-internalize` migration before the first
  standardized routine release.

## Post-deploy verification

Run the required gates in dependency order:

```bash
make foundry-smoke
make -j2 foundry-hosted-e2e foundry-eval
make foundry-telemetry
make foundry-verify
make foundry-evidence
```

If the deployed frontend is in scope, also run:

```bash
cd frontend && PLAYWRIGHT_BASE_URL="$WEB_URL" npm run test:e2e
```

## Destructive exception

The only destructive server-reset path is:

```bash
make foundry-postgres-rebuild
```

It verifies the canonical subscription, resource group, server identity,
location, bootstrap mode, and recreation capacity before deleting anything.

## Output

Report the environment used, per-stage timing, smoke/E2E/eval/telemetry results,
and any blockers or recovery actions.
