---
name: azure-validation
description: Validate a deployable or deployed public Foundry-hosted workflow without deploying resources.
---

# Azure Validation Skill

Use this skill after IaC review and before deployment. Validate readiness and live behavior without running deployment commands that mutate Azure resources.

## Required inputs

- `infra/foundry-hosted/azure.yaml`, `.azure/deployment-plan.md`, and public
  Foundry Bicep files identify the intended existing-resource target and
  lane-owned resource model.
- If live resources already exist, the active Azure subscription and environment are known.

## Local validation

Run non-mutating checks only:

```bash
cd infra/foundry-hosted && azd provision --preview
az bicep build --file infra/foundry-hosted/iac/main.bicep
cd ../..
make foundry-package
```

Review every preview change. A preview that replaces PostgreSQL, shared Foundry
resources, monitoring, ACR, or unreviewed RBAC is a blocker. Package validation
must use `make foundry-package` so the generated hosted context is fresh. Do
not add new tools solely for validation.

## Smoke and behavior checks

- Validate the public Foundry Responses endpoint with `make foundry-smoke`.
- Run `scripts/foundry/hosted_e2e.sh` for conversation, approval, rejection, and
  duplicate-response behavior.
- Run Playwright against the public frontend when it is deployed:

```bash
PLAYWRIGHT_BASE_URL="$WEB_URL" make test-e2e
```

  This must prove the public frontend is wired through its same-origin proxy to
  the internal API, including
  Workflow History loading JSON successfully.
- Confirm only the lane-specific Bicep-managed identities/roles are present:
  registry-pull `AcrPull` and backend Azure AI User at the existing Foundry
  project. Evaluation storage, PostgreSQL, monitoring configuration, and
  Foundry connections are existing operational prerequisites, not Bicep-managed
  resources.

## Pass/fail behavior

- Pass only when preview, Bicep build, package validation, Foundry smoke/E2E,
  applicable hosted UI checks, workflow cases, and RBAC checks succeed.
- If blocked, report the exact failing command, missing resource, or permission gap and do not deploy.
