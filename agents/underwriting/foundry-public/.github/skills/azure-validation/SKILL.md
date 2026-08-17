---
name: azure-validation
description: Validate the underwriting public Foundry lane and deployed behavior without running deployment mutations.
---

# Azure Validation Skill

Use this skill after IaC review and before deployment. Validate readiness and live behavior without mutating Azure resources.

## Required inputs

- Active Azure subscription and authenticated `azd` environment
- `infra/foundry-hosted/azure.yaml` and `infra/foundry-hosted/iac/main.bicep`
- Existing deployed frontend and hosted agent URLs when live validation is expected

## Non-mutating checks

Run:

```bash
make foundry-bootstrap
make foundry-iac-build
cd infra/foundry-hosted && AZURE_DEV_USER_AGENT=microsoft_foundry_skill azd provision --preview
make foundry-postgres-readiness
```

## Behavior checks

- Validate hosted workflow invocation:

```bash
make foundry-smoke
```

- Validate report-only hosted trace evaluation when runtime or telemetry behavior is in scope:

```bash
make foundry-eval
```

- Validate deployed frontend parity when a public URL is available:

```bash
cd frontend && PLAYWRIGHT_BASE_URL="$WEB_URL" npm run test:e2e
```

## Pass/fail behavior

- Pass only when preview/build/readiness succeed and any required live smoke/evaluation checks pass.
- If blocked, report the exact failing command, missing permission, missing environment value, or unavailable live endpoint and do not deploy.
