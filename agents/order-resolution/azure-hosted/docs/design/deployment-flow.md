# Deployment Flow

## Bootstrap

`infra/azure-apphosted/iac/main.bicep` targets subscription scope and asserts
the exact subscription, resource group, and region. Modules create monitoring,
ACR, Foundry inference/evaluation resources, PostgreSQL, managed identities,
RBAC, the Container Apps environment, and two Container Apps.

Bootstrap requires PostgreSQL Entra administrator object/name values. It runs
a non-interactive infrastructure preview and stops on delete or replace
operations. It generates the separate PostgreSQL server-creation password into
local AZD environment state, enables dual Entra/password authentication, and
never writes that secret to the profile or release evidence. Reuse mode is
non-mutating.

## Routine app-only release

`make azure-release`:

1. preflight/readiness and target guards;
2. local validation and Bicep build in parallel;
3. model/quota preflight;
4. parallel ACR builds and immutable digest capture;
5. parallel backend/frontend Container App updates;
6. verify the exact two-app inventory, internal backend, external frontend,
   proxy, probes, exact images, PostgreSQL security posture, and an empty
   Foundry agent application/version inventory;
7. health smoke;
8. low-risk, damaged-item, and high-value HITL domain E2E;
9. hosted-browser Playwright;
10. report-only Foundry evaluation and App Insights correlation;
11. secret-free evidence/timing aggregation.

There is no hosted-agent deploy, version activation, or invocation leg.
