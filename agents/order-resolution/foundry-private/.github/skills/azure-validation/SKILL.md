---
name: azure-validation
description: Validate a deployable or deployed private-network Foundry workflow without deploying resources.
---

# Azure Validation Skill

Use this skill after IaC review and before deployment. Validate readiness and
live behavior without running commands that mutate Azure resources.

## Private lane contract

- Application BYO VNet: `10.74.0.0/16`.
- Foundry BYO VNet: `10.76.0.0/16`.
- Foundry integration subnet: `10.76.0.0/24`.
- Foundry dependency endpoint subnet: `10.76.1.0/24`.
- Container Apps subnet: `10.74.2.0/23`.
- Private endpoint subnet: `10.74.4.0/24`.
- Private runner subnet: `10.74.5.0/27`.
- The external frontend is the only public ingress. The FastAPI wrapper,
  Foundry, PostgreSQL, ACR, and runner are private.
- Private DNS resolution and managed-identity access are prerequisites. A
  validation shell outside the approved private runner cannot prove private
  service reachability.

## Required inputs

- `infra/foundry-hosted/azure.yaml`, `.azure/deployment-plan.md`, and the
  private Foundry Bicep files identify the intended target and lane-owned
  resource model.
- The selected secret-free private deployment profile identifies the target
  subscription, resource group, region, and environment.
- If live resources already exist, the active Azure subscription and private
  runner context are known.

## Local validation

Run non-mutating checks only:

```bash
make foundry-private-what-if
make foundry-private-iac-build
make foundry-private-package
```

Review every preview change. A preview that replaces PostgreSQL, private
Foundry resources, private endpoints, private DNS, monitoring, ACR, or
unreviewed RBAC is a blocker. Package validation must use the repository
command so generated hosted context is fresh. Do not add tools solely for
validation.

## Connectivity and boundary checks

- Resolve Foundry, PostgreSQL, and ACR names from the private runner and verify
  they resolve to private addresses.
- Verify the frontend can reach only the internal wrapper through its same-origin
  `/api` proxy; the browser must not receive a private service endpoint.
- Verify the wrapper can reach private Foundry and PostgreSQL using managed
  identity/TLS and the least-privilege runtime role.
- Verify private ACR image pull and the runner's identity/RBAC without embedding
  credentials.
- Fail closed when private DNS, route tables, endpoint approval, identity
  propagation, or readiness is missing.

## Smoke and behavior checks

- Validate the private Foundry Responses endpoint from the private runner using
  the repository smoke target.
- Run the repository hosted E2E for conversation, approval, rejection, and
  duplicate-response behavior.
- Run Playwright against the external frontend when it is deployed:

```bash
PLAYWRIGHT_BASE_URL="$WEB_URL" make test-e2e
```

  This must prove the external frontend is wired through its same-origin proxy
  to the internal wrapper, including Workflow History loading JSON successfully.
- Confirm only lane-specific managed identities and minimum roles are present.
  Shared-resource RBAC and private endpoint ownership must be explicit; do not
  silently broaden roles to work around connectivity.

## Pass/fail behavior

- Pass only when preview, Bicep build, package validation, private DNS and
  endpoint checks, applicable UI checks, workflow cases, and RBAC checks
  succeed.
- If blocked, report the exact command, missing private resource, failed DNS or
  identity check, or permission gap and do not deploy.
