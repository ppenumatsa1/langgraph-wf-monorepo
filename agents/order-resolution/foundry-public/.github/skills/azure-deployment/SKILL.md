---
name: azure-deployment
description: Execute already validated Azure deployments and verify live endpoints.
---

# Azure Deployment Skill

Use this skill only for deployments that already passed Azure validation. Do not use it to design, prepare, or validate an unvalidated app.

## Hard gates

- Require `.azure/deployment-plan.md` to exist with status `Validated`.
- Run pre-deploy checks before any mutation: active subscription, AZD environment, required variables, Docker availability when needed, and clean authentication to Azure.
- Do not perform destructive cleanup, resource deletion, environment reset, or database drop unless the user explicitly confirms that exact destructive action.

## Deployment sequence

The routine deployment path is the checked-in, authenticated app-only release:

```bash
make foundry-release
```

It reuses the existing PostgreSQL database and retained public-lane
dependencies, performs its selected validation and Bicep build, fresh-packages
the hosted source, deploys backend/frontend/hosted-agent legs, and then gates
on smoke, hosted E2E, evaluation, and telemetry. Do not substitute a bare
`azd deploy` for that release sequence.

Provisioning is an exceptional reconciliation, not the automatic route for
infra/runtime changes:

```bash
make foundry-provision
```

The command runs a non-interactive preview and fails closed on delete or
replace changes.

Use `scripts/skills/deployment-mode-router.sh` to choose quick versus full
*local validation*. Its deployment output must remain `app_only`.

After an approved reconciliation, confirm the retained-resource boundary and
the lane-specific Container App identity/RBAC assignments before application
deployment. Do not create, replace, or rebuild the existing PostgreSQL server
or the existing workflow database.

## Known recovery

If Container Apps deployment fails because the app is not bound to ACR through its managed identity, recover with the explicit registry binding and rerun deploy:

```bash
az containerapp registry set \
  --name <container-app-name> \
  --resource-group <resource-group> \
  --server <acr-login-server> \
  --identity system
azd deploy
```

Use this recovery only for the known registry binding issue; do not mask unrelated deployment failures.

## Post-deploy verification

- Run smoke tests against the live HTTPS endpoint.
- Verify health endpoint, Container Apps revision readiness, and recent logs.
- Run hosted Playwright UI parity against the live frontend:

```bash
PLAYWRIGHT_BASE_URL="<frontend-https-url>" make test-e2e
```

  Fail deployment verification if Workflow History shows `Unexpected token`, `not valid JSON`, or `<!doctype`; that means frontend routing/proxy/API base configuration is returning HTML instead of JSON.
- Validate RBAC live: ACR image pull, Key Vault secret reads, PostgreSQL connectivity, and observability ingestion where applicable.
- Validate `ORD-1001` completes without `hitl.request`.
- Validate `ORD-1009` emits `hitl.request` and completes the expected approval/resume path.
- Confirm backend release images retain
  `PIP_INDEX_URL=https://packagefeedproxy.microsoft.io/pypi/simple`, the
  approved CFS package feed.
- Report the frontend HTTPS endpoint, its `/health` and proxied `/api/health`
  endpoints, and any hosted-agent smoke target. Identify the backend API FQDN
  as internal-only rather than presenting it as browser-accessible.

## Output

Report deployed environment, resource group, Container Apps names, image tags when available, smoke results, RBAC results, and fully qualified HTTPS endpoints. If deployment fails, report the exact command, error, recovery attempted, and next safe action.
