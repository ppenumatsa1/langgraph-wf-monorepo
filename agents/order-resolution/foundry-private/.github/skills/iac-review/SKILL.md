---
name: iac-review
description: Review the private-network Azure and Foundry infrastructure as code without deploying resources.
---

# IaC Review Skill

Use this skill to review Azure/Foundry deployment assets before validation or
deployment. Do not run commands that create, update, or delete cloud
resources.

## Scope

Review only repository deployment assets, including AZD configuration, Bicep
modules, environment parameters, Docker/container settings, private DNS
configuration, and smoke scripts.

## Private network checklist

- Confirm one BYO VNet with address space `10.74.0.0/16`.
- Confirm non-overlapping subnet reservations:
  - Foundry integration `10.74.0.0/24`
  - Container Apps `10.74.2.0/23`
  - private endpoints `10.74.4.0/24`
  - runner `10.74.5.0/27`
- Confirm only the frontend has external ingress. The FastAPI wrapper must use
  internal ingress, and Foundry, PostgreSQL, ACR, and the runner must remain
  private.
- Confirm private endpoints, private DNS zones/links, route dependencies, and
  endpoint approval are explicit for Foundry, PostgreSQL, and ACR.
- Confirm the runner subnet has no public administrative ingress and that its
  identity can perform only the lane's approved automation.
- Confirm Application Insights wiring is explicit without adding LangSmith as a
  dependency.

## Review checklist

- Verify `azure.yaml`, `.azure/deployment-plan.md`, and Bicep files describe one
  coherent private-network deployment path.
- Confirm Bicep manages only the resources intentionally owned by this lane and
  does not silently rebuild retained PostgreSQL, Foundry, monitoring, ACR, or
  shared network resources.
- Review Container Apps ingress, health probes, environment variables, secrets
  references, scaling, CPU/memory, and revision behavior.
- Review ACR integration and image naming; ensure private ACR pulls use managed
  identity/RBAC rather than embedded credentials.
- Review PostgreSQL authentication, private networking, TLS connection-secret
  handling, readiness, and runtime least privilege. Runtime code must not own
  schema DDL or role administration.
- Review private Foundry endpoint/network assumptions, model/SKU/region
  assumptions, managed-identity access, project-scoped Application Insights
  connection, and least-privilege roles.
- Review smoke scripts for deterministic health, workflow, HITL, private DNS,
  and identity assertions without destructive side effects.
- Confirm all preview/provision/release commands are noninteractive and fail
  closed on delete/replace, target drift, missing DNS/RBAC/readiness, or
  secret-bearing artifacts.
- Confirm Dockerfiles retain the approved Microsoft package feeds.
- Flag security issues: plaintext secrets, broad roles, public service
  endpoints, permissive CORS, disabled TLS, missing private DNS, and
  destructive cleanup defaults.

## Output

Report only actionable findings with file paths, risk, and recommended fix. If
no issues are found, state that the private-network IaC review passed without
deployment. Do not report repository configuration as live Azure proof.
