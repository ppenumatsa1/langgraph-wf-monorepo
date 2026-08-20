---
name: azure-deployment
description: Execute already validated private-network Azure deployments and verify the external frontend and internal service boundary.
---

# Azure Deployment Skill

Use this skill only for deployments that already passed Azure validation. Do
not use it to design, prepare, or validate an unvalidated app.

## Private lane overlay

- The target is a BYO VNet with address space `10.74.0.0/16`.
- Reserved subnets are Foundry integration `10.74.0.0/24`, Container Apps
  `10.74.2.0/23`, private endpoints `10.74.4.0/24`, and the private runner
  `10.74.5.0/27`.
- Only the frontend has external ingress. The FastAPI wrapper is internal;
  Foundry, PostgreSQL, ACR, and the runner are private and require private DNS.
- Authenticated deployment runs from the private runner. GitHub Actions does
  not receive Azure credentials and must not mutate resources.
- All commands run noninteractively. Delete/replace previews, unexpected
  targets, missing private DNS/RBAC/readiness, secret prompts, and
  secret-bearing evidence are fail-closed blockers.
- Deployment safety approval is distinct from business HITL. Never bypass the
  LangGraph `interrupt()` / `Command(resume=...)` approval path.

## Hard gates

- Require `.azure/deployment-plan.md` to exist with status `Validated`.
- Run pre-deploy checks before any mutation: active subscription, AZD
  environment, required variables, Docker availability when needed, private
  runner execution, and clean authentication to Azure.
- Run `azd provision --preview --no-prompt` (or the repository equivalent)
  before infrastructure reconciliation and stop on any delete or replace
  operation.
- Do not perform destructive cleanup, resource deletion, environment reset, or
  database drop. A preview that proposes one is a blocker.

## Deployment sequence

The routine deployment path is the checked-in, authenticated app-only release:

```bash
make foundry-private-release
```

It reuses retained private dependencies, performs its selected validation and
Bicep build, fresh-packages the hosted source, deploys the external frontend,
internal wrapper, and private Foundry leg, and then gates on smoke, hosted E2E,
evaluation, and telemetry. Do not substitute a bare `azd deploy` for that
release sequence.

Provisioning is an exceptional reconciliation, not the automatic route for
application changes:

```bash
make foundry-private-provision
```

The command must run a noninteractive preview and fail closed on delete,
replace, target, network, RBAC, readiness, or secret-handling violations.

Use `scripts/skills/deployment-mode-router.sh` to choose quick versus full
*local validation*. Its deployment output must remain `app_only`.

After a passing preview, confirm the retained-resource boundary, private
endpoint/DNS resolution, and lane-specific Container App identity/RBAC
assignments before application deployment. Do not create, replace, or rebuild
the private PostgreSQL server or workflow database as part of an app release.

## Known recovery

If Container Apps deployment fails because the app is not bound to private ACR
through its managed identity, recover with the explicit registry binding and
rerun deploy:

```bash
az containerapp registry set \
  --name <container-app-name> \
  --resource-group <resource-group> \
  --server <acr-login-server> \
  --identity system
azd deploy
```

Use this recovery only for the known registry binding issue; do not mask
unrelated failures or weaken private endpoint requirements.

## Post-deploy verification

- Run smoke tests against the live external frontend HTTPS endpoint.
- Verify frontend revision readiness, internal wrapper readiness, private DNS
  resolution, and recent logs from the private runner or approved operator
  context.
- Run hosted Playwright UI parity against the live frontend:

```bash
PLAYWRIGHT_BASE_URL="<frontend-https-url>" make test-e2e
```

  Fail deployment verification if Workflow History shows `Unexpected token`,
  `not valid JSON`, or `<!doctype`; that means frontend routing/proxy/API base
  configuration is returning HTML instead of JSON.
- Validate RBAC live: private ACR image pull, private PostgreSQL connectivity,
  private Foundry invocation, and Application Insights ingestion where
  applicable.
- Validate `ORD-1001` completes without `hitl.request`.
- Validate `ORD-1009` emits `hitl.request` and completes the expected
  approval/resume path.
- Confirm release images retain the approved Microsoft package feeds.
- Identify the wrapper API FQDN as internal-only rather than presenting it as
  browser-accessible. Do not expose private Foundry, PostgreSQL, ACR, or runner
  endpoints in browser configuration or release evidence.

## Output

Report the selected private environment, resource group, Container Apps names,
private endpoint/DNS checks, image digests, smoke results, RBAC results, and
frontend HTTPS endpoint. If deployment fails, report the exact command,
fail-closed blocker, recovery attempted, and next safe action. Do not convert
repository configuration into a live Azure success claim.
