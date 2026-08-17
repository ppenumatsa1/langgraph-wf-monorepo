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

## Open deployment prerequisites

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
