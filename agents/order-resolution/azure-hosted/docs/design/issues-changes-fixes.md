# Issues, Changes, and Fixes

## Azure-hosted lane

- Removed the Foundry Responses application-host service and all agent
  container/version/invocation release behavior.
- Runs the authoritative `StateGraph` directly in the internal FastAPI
  Container App.
- Added root `azure.yaml` with exactly backend/frontend Container App services.
- Added modular subscription-scope Bicep with exact-target assertions,
  bootstrap/reuse separation, stable names, identities, RBAC, ACR, monitoring,
  PostgreSQL, Foundry model deployments, and health probes.
- Added immutable parallel image builds, app-only deployment, topology/image
  verification, low-risk/HITL domain E2E, browser E2E, report-only evaluation,
  telemetry correlation, and secret-free evidence/timings.
- Kept native SSE, deterministic HITL, idempotency, PostgreSQL audit, and
  redacted AG-UI/CopilotKit contracts.
- Enabled coherent PostgreSQL dual authentication: administrator-owned Entra
  DDL plus a least-privilege runtime password role; the server bootstrap secret
  is generated only into local AZD state.
- Pinned the backend to one replica until distributed PostgreSQL admission
  locking exists and made same-decision HITL resume claiming atomic.
- Added interprocess release-evidence locking and unique fsync'd atomic files.
- Strengthened live verification to require exactly the expected two Container
  Apps and zero Foundry agent applications/versions.
- Moved PostgreSQL Entra-administrator reconciliation after ARM provisioning so
  server reconciliation cannot race the administrator child resource.
- Changed ACR to the subscription-supported Premium SKU.
- Granted the Foundry project identity read access to Application Insights and
  Log Analytics for report-only evaluations.
- Disabled Azure Monitor trace sampling for release workloads so bounded
  telemetry correlation cannot silently omit an E2E conversation.
- Replaced trace-content evaluation with ephemeral synthetic workflow snapshots;
  Application Insights remains redacted while Foundry task-completion and
  coherence graders receive the required user/assistant pair in memory.
- Fixed deterministic order extraction so ORD-1002 through ORD-1010 no longer
  collapse to ORD-1001, and strengthened E2E assertions to validate the terminal
  workflow output rather than matching the original input.

## Accepted release

- Release: `order-resolution-azure-20260817T210042Z-623966`
- Source commit: `0d22e98`
- IaC convergence: 2m 41s
- Full app release: 8m 39.427s
- Local gates: 78 backend tests, 11/11 deterministic evaluations, and 10/10
  browser tests.
- Azure gates: smoke passed, 3/3 domain E2E passed, and 10/10 browser E2E
  passed.
- Foundry report-only evaluation: 3/3 passed, zero failed, zero errored.
- Application Insights: all three release conversations correlated across 92
  rows with zero exceptions.
- Runtime topology: exactly two Container Apps, internal backend, external
  frontend, backend maximum one replica, and zero Foundry hosted-agent
  applications or versions.
- Public frontend:
  `https://orderresolution-jed2e5qyaxlau-we.wittyriver-92c74877.eastus2.azurecontainerapps.io`

## Deployment prerequisites

- Azure CLI/AZD authentication and permission to create subscription/resource
  group deployments, role assignments, Cognitive Services deployments,
  PostgreSQL, ACR, monitoring, and Container Apps.
- East US 2 model quota/capacity.
- Entra PostgreSQL administrator object ID and principal name.
- Public operator IP for schema setup when required.
- Generated least-privilege runtime database password stored only in local AZD
  environment/container secret state.
- Public POC database networking uses the Azure-services firewall rule with
  TLS and a restricted runtime role. Production is blocked until private
  networking or deterministic controlled egress replaces it.
