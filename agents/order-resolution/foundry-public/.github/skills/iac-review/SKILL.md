---
name: iac-review
description: Review Azure and Foundry infrastructure as code without deploying resources.
---

# IaC Review Skill

Use this skill to review Azure/Foundry deployment assets before validation or deployment. Do not run commands that create, update, or delete cloud resources.

## Scope

Review only repository deployment assets, including AZD configuration, Bicep modules, environment parameters, Docker/container settings, and smoke scripts.

## Review checklist

- Verify `azure.yaml`, `.azure/deployment-plan.md`, and Bicep files describe one coherent existing-resource deployment path.
- Confirm Bicep treats the Container Apps environment, ACR, Foundry
  account/project/model deployments, Application Insights, Foundry
  connections/evaluation storage, and PostgreSQL server/database as retained
  dependencies. It may manage only the lane-specific frontend/backend Container
  Apps, registry-pull identity, and scoped role assignments.
- Review Container Apps ingress, health probes, environment variables, secrets references, scaling, CPU/memory, and revision behavior.
- Review ACR integration and image naming; ensure Container Apps can pull images using managed identity/RBAC rather than embedded credentials.
- Review the existing Azure Database for PostgreSQL networking,
  authentication, TLS connection-secret handling, and region assumptions; do
  not propose database creation, rebuild, or destructive administration.
- Review application secret references without assuming a Key Vault resource is
  declared by this lane.
- Review Application Insights and Log Analytics wiring, retention, sampling assumptions, and required app settings.
- Review managed identities and RBAC assignments for least privilege across the
  lane's ACR pull and Foundry project access; shared-resource RBAC remains
  outside this template.
- Confirm region and SKU assumptions are explicit and compatible across the
  retained Container Apps environment, ACR, PostgreSQL, monitoring, and
  Foundry resources.
- Review Azure AI Foundry resources for the public project, model/SKU/region
  assumptions, managed-identity access, project-scoped Application Insights
  connection, and least-privilege roles.
- Check smoke scripts for deterministic health, workflow, HITL, and RBAC assertions without destructive side effects.
- Confirm Dockerfiles retain
  `PIP_INDEX_URL=https://packagefeedproxy.microsoft.io/pypi/simple`, the
  approved CFS package feed.
- Flag security issues: plaintext secrets, broad roles, public admin endpoints, permissive CORS, disabled TLS, weak network posture, and destructive cleanup defaults.

## Output

Report only actionable findings with file paths, risk, and recommended fix. If no issues are found, state that IaC review passed without deployment.
