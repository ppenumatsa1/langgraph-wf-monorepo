# Underwriting LangGraph Public Deployment Plan

> **Status:** Validated

Generated: 2026-08-16

## 1. Project Overview

**Goal:** Deploy the existing LangGraph underwriting lane through Azure
Developer CLI and Bicep, then prove the full hosted smoke, E2E, evaluation,
telemetry, timing, and evidence lifecycle.

**Path:** Modernize existing application.

## 2. Requirements

| Attribute | Value |
| --- | --- |
| Classification | Development / POC |
| Scale | Small |
| Budget | Balanced |
| Subscription | `7df95e88-701c-4693-af77-3159f83b558d` |
| Location | `eastus2` |
| Resource group | `rg-langgraph-uw-foundry-public` |
| Environment | `underwriting-foundry-public` |

The user previously approved autonomous deployment to the same subscription
and location used by the completed order-resolution lane.

## 3. Components Detected

| Component | Type | Technology | Path |
| --- | --- | --- | --- |
| Underwriting API | Internal API | FastAPI, LangGraph, Python | `backend/` |
| Operations console | Public frontend | React, Vite, Nginx | `frontend/` |
| Hosted workflow | Agent | Foundry Responses 2.0, LangGraph | `backend/foundry/` |
| Infrastructure | IaC | AZD and Bicep | `infra/foundry-hosted/` |

## 4. Recipe Selection

**Selected:** AZD with existing Bicep.

**Rationale:** The lane already contains reviewed `azure.yaml`, Bicep modules,
Dockerfiles, immutable-image release scripts, deployment profiles, and
release-evidence automation.

## 5. Architecture

```text
browser
  -> external React/Nginx Container App
  -> same-origin /api proxy
  -> internal FastAPI Container App
  -> Foundry Responses 2.0 hosted LangGraph agent
  -> Azure Database for PostgreSQL Flexible Server
```

| Component | Azure Service | SKU / mode |
| --- | --- | --- |
| Frontend | Azure Container Apps | Consumption |
| Backend | Azure Container Apps | Consumption, internal ingress |
| Hosted workflow | Microsoft Foundry hosted agent | Responses 2.0 |
| Database | PostgreSQL Flexible Server | Burstable development tier |
| Images | Azure Container Registry | Basic |
| Models | Foundry model deployments | DataZoneStandard: 1500/250/120 |
| Monitoring | Application Insights + Log Analytics | Workspace based |
| Evaluation artifacts | Storage account | Standard LRS |

Managed identities and scoped RBAC provide ACR pull, Foundry model access,
telemetry, and runtime connectivity. PostgreSQL schema DDL remains
administrator-owned; runtime credentials are least privilege.

## 6. Provisioning Limit Checklist

| Resource type | Number to deploy | Expected total in lane RG | Limit / quota | Notes |
| --- | ---: | ---: | ---: | --- |
| `Microsoft.App/managedEnvironments` | 1 | 5 subscription usage | 50 | `az quota`: 4 used, 46 available |
| `Microsoft.App/containerApps` | 2 | 2 | 100 per environment | Azure service limit; below limit |
| `Microsoft.ContainerRegistry/registries` | 1 | 1 | 100 per subscription | Azure service limit; below limit |
| `Microsoft.DBforPostgreSQL/flexibleServers` | 1 | 1 | 20 default per region | Azure service limit; below limit |
| `Microsoft.CognitiveServices/accounts` | 1 | 1 | 200 per region | Azure service limit; below limit |
| GPT Standard/DataZoneStandard TPM | 1750K total | 4500K subscription usage after lane | 5000K | Existing order lane uses 2000K; underwriting requests 1750K |
| Embeddings Standard/DataZoneStandard TPM | 120K | 240K after lane | Validated model quota | Underwriting requests 120K |
| `Microsoft.OperationalInsights/workspaces` | 1 | 1 | 1000 per subscription | Azure service limit; below limit |
| `Microsoft.Insights/components` | 1 | 1 | No blocking count quota found | Workspace based |
| `Microsoft.Storage/storageAccounts` | 1 | 5 regional usage | 250 | `az quota`: 4 used, 246 available |

**Status:** Live quota checks passed for Container Apps and Storage. Foundry
model quota is validated by the lane model-preflight gate; unsupported
count-based providers use documented service limits and deployment preview.

## 7. Execution Checklist

### Planning

- [x] Analyze workspace
- [x] Gather requirements
- [x] Confirm subscription and location from prior explicit approval
- [x] Scan codebase
- [x] Select recipe
- [x] Plan architecture
- [x] User approved autonomous completion of this lane
- [x] Fetch live quotas and validate capacity

### Preparation

- [x] Existing AZD, Bicep, Docker, release, and evidence artifacts reviewed
- [x] Full local lifecycle passed
- [x] PostgreSQL bootstrap and least-privilege grants corrected
- [x] Set status to `Ready for Validation`

### Validation

- [x] Invoke azure-validate
- [x] All validation checks pass
  - [x] 1. AZD Installation
  - [x] 2. Schema Validation
  - [x] 3. Environment Setup
  - [x] 4. Authentication Check
  - [x] 5. Subscription/Location Check
  - [x] 6. Aspire Pre-Provisioning Checks - not applicable
  - [x] 7. Provision Preview
  - [x] 8. Build Verification
  - [x] 9. Docker Build Context Validation
  - [x] 10. Package Validation
  - [x] 11. Azure Policy Validation
  - [x] 12. Aspire Post-Provisioning Checks - not applicable
- [x] Validation proof populated by azure-validate

### Deployment

- [ ] Invoke azure-deploy
- [ ] Provision and deploy
- [ ] Hosted smoke and E2E pass
- [ ] Foundry evaluation passes
- [ ] Application Insights telemetry passes
- [ ] Secret-free release evidence finalized

## Section 7: Validation Proof

| Check | Command | Result | Timestamp |
| --- | --- | --- | --- |
| AZD and authentication | `azd version`; `azd auth login --check-status` | Passed: azd 1.31.1, authenticated user | 2026-08-16T20:38Z |
| Manifest schema | Azure MCP `validate_azure_yaml` | Passed stable schema | 2026-08-16T20:42Z |
| Target environment | `foundry-profile-apply`; `foundry-bootstrap-env`; `azd env get-values` | Passed for approved subscription, RG, and eastus2 | 2026-08-16T20:42Z |
| Quota | Azure quota CLI for Microsoft.App and Microsoft.Storage | 46 managed environments and 246 storage accounts available | 2026-08-16T20:36Z |
| Local lifecycle | `make validate-full` | Passed in 51.80s: 47 backend tests, frontend build, 24 script tests, Playwright rubric | 2026-08-16T20:35Z |
| Bicep | `make foundry-iac-build` | Passed | 2026-08-16T20:39Z |
| Package | `make foundry-package` | Passed all services in 2m36s | 2026-08-16T20:41Z |
| Provision preview | `azd provision --preview --no-prompt` | Passed in 28.73s: 14 create-only resources, no deletion/replacement | 2026-08-16T20:42Z |
| Docker contexts | Dockerfile and lock-file checks | Passed | 2026-08-16T20:43Z |
| Azure Policy | `az policy assignment list --disable-scope-strict-match` | Three Defender assignments reviewed; no deny policy blocks target | 2026-08-16T20:43Z |
| Deployer RBAC | `az role assignment list --assignee ... --all` | Owner and Foundry User at subscription | 2026-08-16T20:43Z |

**Validated by:** azure-validate workflow

## 9. Files

| File | Purpose | Status |
| --- | --- | --- |
| `.azure/deployment-plan.md` | Deployment source of truth | Created |
| `infra/foundry-hosted/azure.yaml` | AZD service definition | Existing |
| `infra/foundry-hosted/iac/main.bicep` | Infrastructure | Existing |
| `backend/Dockerfile` | Internal API image | Existing |
| `frontend/Dockerfile` | Public frontend image | Existing |
| `infra/foundry-hosted/agent/Dockerfile` | Hosted-agent image | Existing |

## 10. Stop Conditions

- Any previewed deletion or replacement of stateful resources.
- Subscription, region, profile, or resource-group mismatch.
- Insufficient model quota.
- Runtime PostgreSQL DDL or excessive grants.
- Public backend ingress, mutable image tags, leaked secrets, or stale evidence.
